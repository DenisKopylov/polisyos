import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";

import {
  buildCohortTimeTravelerView,
  buildIdentifiabilitySurfaceView,
  buildScientificDepthSnapshot,
  buildSensitivityRotorView,
  buildStressTestTheatreView,
} from "./scientificDepth";

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
            populationShare: 0.42,
            primaryDelta: 0.2,
          },
          {
            cohortLabel: "South",
            direction: "negative",
            isVulnerable: true,
            populationShare: 0.18,
            primaryDelta: -0.1,
          },
          {
            cohortLabel: "Rural",
            direction: "flat",
            isVulnerable: true,
            populationShare: 0.08,
            primaryDelta: 0,
          },
        ],
      },
    ],
    giniAfter: 0.32,
    giniBefore: 0.34,
    giniDelta: -0.02,
    losersCount: 1,
    losersShare: 0.18,
    vulnerableLosersCount: 1,
    winnersCount: 1,
    winnersShare: 0.42,
  },
  generatedAt: "2026-04-01T12:00:00.000Z",
  interventionCount: 1,
  issues: {
    blockedPasses: [],
    blockerCount: 0,
    infoCount: 0,
    warningCount: 1,
  },
  keyMetrics: [
    {
      identifiability: "identified",
      ciLevel: 0.95,
      ciLower: 0.2,
      ciUpper: 2.1,
      effectSize: 1.2,
      formatted: "+1.20",
      name: "GDP lift",
      pValue: 0.01,
      unit: "%",
      value: 1.2,
    },
    {
      assumptionWarnings: ["unmeasured confounder"],
      identifiability: "assumed",
      ciLevel: 0.95,
      ciLower: 0.1,
      ciUpper: 0.2,
      effectSize: 0.15,
      formatted: "+0.15",
      name: "Employment lift",
      unit: "%",
      value: 0.15,
    },
    {
      assumptionWarnings: ["instrument missing"],
      identifiability: "estimated",
      ciLevel: null,
      ciLower: null,
      ciUpper: null,
      effectSize: 0.3,
      formatted: "+0.30",
      name: "Inflation risk",
      unit: "%",
      value: 0.3,
    },
    {
      ciLevel: null,
      ciLower: null,
      ciUpper: null,
      effectSize: 0.05,
      formatted: "7.00",
      name: "Coverage gap",
      unit: "pts",
      value: 7,
    },
  ],
  metricComparisons: [],
  metricValidationFamilyAdjustment: null,
  policySummary: "Approve the policy with monitoring.",
  runId: "run-33",
  sourceKind: "decision_packet",
  totalDurationMs: 1200,
  verdict: "APPROVE",
};

const evidenceContext: RunEvidenceContext = {
  dataNeeds: [
    {
      geography: "UA",
      granularity: "monthly",
      matchedPlanIds: [],
      metric: "Coverage gap",
      needId: "need-identification",
      notes: [],
      purpose: "identification",
      qualityMin: 0.8,
      timeEnd: "2026",
      timeStart: "2024",
    },
  ],
  dataSnapshotRef: null,
  evidenceBundleRef: null,
  executionPlanRef: null,
  fetchPlans: [
    {
      connectorId: "stat-office",
      datasetId: "labor-panel",
      dateEnd: null,
      dateStart: null,
      fallbackCount: 0,
      filters: {},
      granularity: "monthly",
      matchedNeedIds: ["need-identification"],
      metricId: "employment",
      notes: [],
      planId: "plan-confounder-panel",
      profileId: null,
      qualityMin: 0.8,
      sourceLane: "fastlane",
    },
  ],
  inputBindingsRef: null,
  promotionCandidates: [
    {
      confidence: 0.91,
      connectorId: "stat-office",
      createdAt: "2026-03-28T08:00:00.000Z",
      datasetId: "gdp-panel",
      matchedPlanId: "plan-confounder-panel",
      metadata: {},
      metricId: "gdp",
      profileId: null,
      promotionId: "promotion-gdp",
      signals: ["fresh"],
      sourceLane: "explorelane",
      status: "green",
    },
  ],
  relatedArtifacts: [],
  runId: "run-33",
  sourceKind: "core_run",
  warnings: ["freshness warning"],
};

const governanceIssues: GovernanceIssueView[] = [
  {
    code: "legal_blocker",
    durationMs: 20,
    message: "Legal approval missing",
    passId: "legal-pass",
    path: null,
    raw: {},
    severity: "blocker",
  },
  {
    code: "fairness_warning",
    durationMs: 15,
    message: "Disparate impact ratio is below policy target",
    passId: "fairness-pass",
    path: null,
    raw: {},
    severity: "warning",
  },
  {
    code: "missing_data",
    durationMs: 10,
    message: "Missing protected-attribute data",
    passId: "data-pass",
    path: null,
    raw: {},
    severity: "info",
  },
];

describe("scientific depth domain", () => {
  it("preserves producer identifiability without inferring it from warnings or bounds", () => {
    const surface = buildIdentifiabilitySurfaceView({
      decisionView,
      evidenceContext,
    });

    expect(surface.cells.map((cell) => [cell.label, cell.state])).toEqual([
      ["GDP lift", "identified"],
      ["Employment lift", "assumed"],
      ["Inflation risk", "estimated"],
      ["Coverage gap", "unknown"],
    ]);
    expect(surface.summary).toEqual([
      { count: 1, state: "identified" },
      { count: 1, state: "assumed" },
      { count: 1, state: "estimated" },
      { count: 1, state: "unknown" },
    ]);
    expect(surface.totalDecisionBearingQuantities).toBe(6);
    expect(surface.initialCellId).toBe("gdp-lift");
    expect(
      surface.cells.find((cell) => cell.id === "employment-lift")?.bounds
        .method,
    ).toBeNull();
    expect(
      surface.cells.find((cell) => cell.id === "coverage-gap")?.remedy,
    ).toMatchObject({
      effort: "high",
      kind: "dataset",
      ref: "need-identification",
    });
    expect(
      surface.cells.find((cell) => cell.id === "coverage-gap")?.remedies,
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          kind: "dataset",
          ref: "need-identification",
        }),
      ]),
    );
  });

  it("keeps identical warning and bound shapes at producer-declared states", () => {
    const identicalShape = decisionView.keyMetrics.slice(0, 2).map((metric) => ({
      ...metric,
      assumptionWarnings: ["same warning"],
      ciLower: 0,
      ciUpper: 1,
    }));

    const surface = buildIdentifiabilitySurfaceView({
      decisionView: { ...decisionView, keyMetrics: identicalShape },
    });

    expect(surface.cells.map((cell) => cell.state)).toEqual([
      "identified",
      "assumed",
    ]);
  });

  it("extinguishes claims under an E-value threshold and flags gate changes", () => {
    const rotor = buildSensitivityRotorView({
      decisionView,
      governanceIssues,
      threshold: 1.5,
    });

    expect(rotor.totalClaims).toBe(4);
    expect(rotor.decisionBearingTotal).toBe(6);
    expect(rotor.decisionBearingExtinguished).toBe(5);
    expect(rotor.decisionBearingExtinguishedShare).toBeCloseTo(5 / 6, 4);
    expect(rotor.extinguishedClaims).toBe(3);
    expect(rotor.remainingClaims).toBe(1);
    expect(rotor.verdictChanged).toBe(true);
    expect(rotor.fairnessGateChanged).toBe(true);
    expect(
      rotor.claims
        .filter((claim) => claim.extinguished)
        .map((claim) => claim.id),
    ).toEqual(["employment-lift", "inflation-risk", "coverage-gap"]);
  });

  it("builds a valid-time cohort flow with policy overlay states", () => {
    const traveler = buildCohortTimeTravelerView({
      activeIndex: 9,
      decisionView,
    });

    expect(traveler.activeIndex).toBe(2);
    expect(traveler.filters).toEqual([
      { id: "dimension", label: "dimension", value: "Region" },
      { id: "policy", label: "policy", value: "APPROVE" },
    ]);
    expect(traveler.policyOverlay).toEqual({
      ref: "policy-overlay:run-33:APPROVE",
      verdict: "APPROVE",
    });
    expect(
      traveler.transitions.map((transition) => transition.policyEffect),
    ).toEqual(["pass", "fail", "review"]);
    expect(traveler.transitions[1]).toMatchObject({
      cohortLabel: "South",
      baselineShare: 0.28,
      fromState: "covered-vulnerable",
      observedShare: 0.18,
      toState: "at-risk-under-policy",
    });
    expect(traveler.transitions[1]?.overlayShare).toBeCloseTo(0.08, 4);
  });

  it("cites the strongest stress scene that justifies a block or warning", () => {
    const theatre = buildStressTestTheatreView({
      decisionView,
      evidenceContext,
      governanceIssues,
      runId: "run-33",
    });

    expect(theatre.summary).toEqual({ blocked: 1, warned: 3 });
    expect(theatre.citedSceneRef).toBe("stress:run-33:legal-blocker");
    expect(
      theatre.scenes.find((scene) => scene.id === "legal-blocker"),
    ).toMatchObject({
      act: 3,
      actual: "block",
      expected: "warn",
      issueRefs: ["legal_blocker"],
      policyChanged: true,
      reactionKey: "phase33.stress.reaction.block",
    });
    expect(
      theatre.scenes.find((scene) => scene.id === "stale-evidence")?.actual,
    ).toBe("warn");
  });

  it("builds the full scientific-depth snapshot for decision packet integration", () => {
    const snapshot = buildScientificDepthSnapshot({
      activeCohortIndex: 1,
      decisionView,
      evidenceContext,
      governanceIssues,
      runId: "run-33",
      sensitivityThreshold: 1.5,
    });

    expect(snapshot.identifiability.cells).toHaveLength(4);
    expect(snapshot.sensitivity.verdictChanged).toBe(true);
    expect(snapshot.cohort.transitions).toHaveLength(3);
    expect(snapshot.stress.citedSceneRef).toBe("stress:run-33:legal-blocker");
  });
});
