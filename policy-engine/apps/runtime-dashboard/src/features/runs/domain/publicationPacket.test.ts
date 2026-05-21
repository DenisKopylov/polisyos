import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";

import {
  buildPublicDecisionPacket,
  buildSignedPublicDecisionPacket,
  packetContainsPrivateContext,
  signPublicDecisionPacket,
  verifySignedPublicDecisionPacket,
} from "./publicationPacket";

const decisionView: DecisionCardViewModel = {
  confidence: "HIGH",
  diagnosticsBadges: [],
  distributional: {
    breakdowns: [
      {
        dimensionLabel: "Protected group",
        rows: [
          {
            cohortLabel: "Reference group",
            direction: "positive",
            isVulnerable: false,
            populationShare: 0.5,
            primaryDelta: 0.04,
          },
          {
            cohortLabel: "Appeal cohort",
            direction: "negative",
            isVulnerable: true,
            populationShare: 0.2,
            primaryDelta: -0.03,
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
    warningCount: 0,
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
  policySummary: "Approve with published safeguards.",
  runId: "run-35",
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
    {
      geography: "Low coverage region",
      granularity: "monthly",
      matchedPlanIds: [],
      metric: "employment",
      needId: "need-2",
      notes: [],
      purpose: "publication",
      qualityMin: 0.35,
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
  runId: "run-35",
  sourceKind: "core_run",
  warnings: [],
};

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

function issue(): GovernanceIssueView {
  return {
    code: "public_rebuttal",
    durationMs: 10,
    message: "private reviewer note: secret raw restricted value SSN-123",
    passId: "governance-pass",
    path: null,
    raw: {
      secret: "SSN-123",
    },
    severity: "warning",
  };
}

describe("publication packet domain", () => {
  it("builds E1-E6 and F1-F5 publication surfaces from public inputs", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-35",
    });

    expect(packet.schema).toBe("polisyos.public_decision_packet.v1");
    expect(packet.argumentMap.nodes.map((node) => node.kind)).toEqual([
      "claim",
      "grounds",
      "warrant",
      "backing",
      "rebuttal",
    ]);
    expect(packet.deterministicExplanations[0]?.narrative).toContain(
      "GDP Change is +1.20%",
    );
    expect(packet.glossary.map((term) => term.term)).toContain("provenance");
    expect(packet.confidenceLadder.map((item) => item.rung)).toContain(
      "weakest_link",
    );
    expect(packet.modelCard.references.length).toBeGreaterThanOrEqual(2);
    expect(packet.coverageCaveat.status).toBe("caveat");
    expect(packet.thresholdContract.policyRef).toBe("policy:run-35");
    expect(packet.bureaucraticForms.map((form) => form.genre)).toEqual([
      "nakaz",
      "rozporiadzhennia",
      "postanova",
      "vysnovok",
    ]);
  });

  it("signs and verifies immutable public packets without privileged context", () => {
    const signed = buildSignedPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-35",
    });

    expect(signed.publicUrlPath).toMatch(/^\/public\/decisions\//u);
    expect(signed.signature).toMatch(/^sig:/u);
    expect(signed.projectionSemantics.primaryState).toBe("projection_only");
    expect(signed.projectionSemantics.authorityRole).toBe("projection_only");
    expect(verifySignedPublicDecisionPacket(signed.signedId)).toMatchObject({
      valid: true,
    });
    const tamperedSuffix = signed.signedId.endsWith("0") ? "1" : "0";
    expect(
      verifySignedPublicDecisionPacket(
        `${signed.signedId.slice(0, -1)}${tamperedSuffix}`,
      ),
    ).toMatchObject({
      reason: "bad_signature",
      valid: false,
    });
  });

  it("blocks publishable Policy Design Case projection labels without making dashboard state authoritative", () => {
    const signed = buildSignedPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      policyDesignCaseProjection: {
        authority_role: "projection_only",
        labels: [
          {
            authority_role: "projection_only",
            label: "publishable",
            state: "publishable",
          },
          {
            authority_role: "projection_only",
            label: "projection only",
            state: "projection_only",
          },
        ],
        may_not_be_used_for: ["scorecard_authority"],
        primary_state: "publishable",
        projection_policy: "reads_policy_design_case_only",
        states: ["publishable", "projection_only"],
      },
      runId: "run-35",
    });

    expect(signed.projectionSemantics.primaryState).toBe("blocked");
    expect(signed.projectionSemantics.authorityRole).toBe("projection_only");
    expect(signed.projectionSemantics.labels).toEqual([
      "projection only",
      "blocked projection",
    ]);
    expect(signed.projectionSemantics.mayNotBeUsedFor).toContain(
      "scorecard_authority",
    );
  });

  it("fails closed when projection-only labels claim publishable authority", () => {
    const signed = buildSignedPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      policyDesignCaseProjection: {
        authority_role: "projection_only",
        labels: [
          {
            authority_role: "projection_only",
            label: "publishable",
            state: "publishable",
          },
          {
            authority_role: "projection_only",
            label: "projection only",
            state: "projection_only",
          },
        ],
        may_not_be_used_for: [
          "approval_authority",
          "runtime_closeout_authority",
          "scorecard_authority",
        ],
        primary_state: "publishable",
        projection_policy: "reads_policy_design_case_only",
        states: ["publishable", "projection_only"],
      },
      runId: "run-35",
    });

    expect(signed.projectionSemantics.primaryState).toBe("blocked");
    expect(signed.projectionSemantics.states).toEqual([
      "projection_only",
      "blocked",
    ]);
    expect(signed.projectionSemantics.labels).toEqual([
      "projection only",
      "blocked projection",
    ]);
    expect(signed.projectionSemantics.mayNotBeUsedFor).toEqual(
      expect.arrayContaining([
        "approval_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
      ]),
    );
  });

  it.each(projectionMaskingCases)(
    "fails closed when projection labels mask $caseId evidence",
    ({ code, label }) => {
      const signed = buildSignedPublicDecisionPacket({
        decisionScore: 0.72,
        decisionView,
        evidenceContext,
        governanceIssues: [issue()],
        policyDesignCaseProjection: {
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
        runId: "run-35",
      });

      expect(signed.projectionSemantics.primaryState).toBe("blocked");
      expect(signed.projectionSemantics.states).toEqual([
        "projection_only",
        "blocked",
      ]);
      expect(signed.projectionSemantics.labels).toContain("blocked projection");
      expect(signed.projectionSemantics.failClosedCodes).toContain(code);
      expect(signed.projectionSemantics.maskingCases).toContain(
        code.replace("projection_masked_", ""),
      );
      expect(signed.projectionSemantics.mayNotBeUsedFor).toEqual(
        expect.arrayContaining([
          "approval_authority",
          "runtime_closeout_authority",
          "scorecard_authority",
        ]),
      );
    },
  );

  it("keeps private governance text out of the signed public model", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView: {
        ...decisionView,
        keyMetrics: [
          {
            ...decisionView.keyMetrics[0]!,
            name: "Secret beneficiary SSN-123-45-6789",
          },
        ],
        policySummary:
          "Approve private reviewer note for SSN-123-45-6789 and confidential household 123456789.",
      },
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-35",
    });

    expect(JSON.stringify(packet)).not.toContain("SSN-123");
    expect(JSON.stringify(packet)).not.toContain("123456789");
    expect(JSON.stringify(packet).toLowerCase()).not.toContain("secret");
    expect(JSON.stringify(packet).toLowerCase()).not.toContain(
      "private reviewer",
    );
    expect(JSON.stringify(packet).toLowerCase()).not.toContain("confidential");
    expect(packetContainsPrivateContext(packet)).toBe(false);
  });

  it("uses stable signatures for stable packet content", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: 0.72,
      decisionView,
      evidenceContext,
      runId: "run-35",
    });

    expect(signPublicDecisionPacket(packet).signedId).toBe(
      signPublicDecisionPacket(packet).signedId,
    );
  });
});
