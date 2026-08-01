import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import { isInteractionState } from "@/shared/lib/domain/statusOwnership";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { PolicyDesignCaseProjection } from "@polisyos/runtime-api-client";

import {
  buildPublicDecisionPacket,
  buildSignedPublicDecisionPacket,
  packetContainsPrivateContext,
  signPublicDecisionPacket,
  verifySignedPublicDecisionPacket,
} from "./publicationPacket";

const testDecisionScore = (point: number) =>
  untracedDecisionQuantity({ metricId: "test.decision_score", point });

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

const opaqueProjectionStates = [
  {
    caseId: "missing",
    label: "missing evidence label",
  },
  {
    caseId: "stale",
    label: "stale evidence label",
  },
  {
    caseId: "conflicting",
    label: "conflicting evidence label",
  },
  {
    caseId: "reissued",
    label: "reissued evidence label",
  },
  {
    caseId: "withdrawn",
    label: "withdrawn evidence label",
  },
  {
    caseId: "non_authoritative",
    label: "non-authoritative evidence label",
  },
  {
    caseId: "projection_only",
    label: "projection-only evidence label",
  },
] as const;

function ownerProjection(
  overrides: Partial<PolicyDesignCaseProjection> = {},
): PolicyDesignCaseProjection {
  return {
    audience: "public",
    audit_refs: [],
    authoritative_for: [],
    capability_reality_state: "implemented",
    contested_records: [],
    contract_verification_refs: [],
    contract_verification_status: "not_verified",
    deficit_register: [],
    labels: [],
    may_be_used_for: [],
    omission_manifest: [],
    participation_requirements: [],
    projection_gaps: [],
    redacted: false,
    schema_version: "policyos.runtime.policy_design_case.projection.v1",
    authority_role: "projection_only",
    closeout_truth: {
      blocker_codes: [],
      blockers: [],
      can_closeout: false,
      contested_state: "not_contested",
      limitation_codes: [],
      omission_codes: [],
      status: "owner-limited",
      verdict: "owner-contested",
    },
    evidence_class: "owner-extension",
    generated_at: "2026-04-29T10:00:00.000Z",
    may_not_be_used_for: ["scorecard_authority"],
    primary_state: "novel_owner_state",
    projection_policy: "reads_policy_design_case_only",
    provenance_kind: "runtime_projection",
    states: ["novel_owner_state"],
    surface: "public_decision",
    ...overrides,
  };
}

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
  it("keeps publication argument support candidate-only without local authority statuses", () => {
    const packet = buildPublicDecisionPacket({
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-candidate-argument",
    });

    expect(
      packet.argumentMap.nodes.every((node) => !Object.hasOwn(node, "status")),
    ).toBe(true);
  });

  it("wraps locally derived publication coverage as candidate display state", () => {
    const packet = buildPublicDecisionPacket({
      decisionView,
      evidenceContext,
      governanceIssues: [],
      runId: "run-candidate-coverage",
    });
    const coverage = packet.coverageCaveat as unknown as {
      caveatState: unknown;
      regions: Array<{ displayState: unknown }>;
    };

    expect(isInteractionState(coverage.caveatState)).toBe(true);
    expect(coverage.caveatState).toMatchObject({
      authorityPurpose: "candidate_display",
      purpose: "interaction_only",
    });
    expect(
      coverage.regions.every((region) =>
        isInteractionState(region.displayState),
      ),
    ).toBe(true);
    expect(
      coverage.regions.every((region) => !Object.hasOwn(region, "status")),
    ).toBe(true);
  });

  it("preserves opaque producer projection labels without minting publishability or closeout authority", () => {
    const projection = ownerProjection({
      states: ["novel_owner_state", "publishable"],
    });
    const packet = buildPublicDecisionPacket({
      decisionView,
      evidenceContext,
      governanceIssues: [],
      policyDesignCaseProjection: projection,
      runId: "run-owner-projection",
    });
    const semantics = packet.projectionSemantics as unknown as {
      closeoutTruth: unknown;
      displayStates: unknown[];
      primaryDisplayState: unknown;
    };

    expect(isInteractionState(semantics.primaryDisplayState)).toBe(true);
    expect(semantics.primaryDisplayState).toMatchObject({
      authorityPurpose: "candidate_display",
      label: "novel_owner_state",
      purpose: "interaction_only",
    });
    expect(
      semantics.displayStates.map((state) =>
        isInteractionState(state) ? state.label : null,
      ),
    ).toEqual(["novel_owner_state", "publishable"]);
    expect(semantics.closeoutTruth).toBe(projection.closeout_truth);
    expect(Object.hasOwn(packet.projectionSemantics, "primaryState")).toBe(
      false,
    );
    expect(JSON.stringify(packet.projectionSemantics)).not.toContain(
      "blocked projection",
    );
  });

  it("builds E1-E6 and F1-F5 publication surfaces from public inputs", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: testDecisionScore(0.72),
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
    expect(packet.confidenceLadder).toHaveLength(1);
    expect(packet.confidenceLadder[0]).toMatchObject({
      rung: null,
      score: {
        lineage: {
          reason_code: "owner_confidence_quantity_absent",
        },
        point: null,
      },
    });
    expect(packet.modelCard.references.length).toBeGreaterThanOrEqual(2);
    expect(packet.coverageCaveat.caveatState.label).toBe("caveat");
    expect(packet.thresholdContract.policyRef).toBe("policy:run-35");
    expect(packet.bureaucraticForms.map((form) => form.genre)).toEqual([
      "nakaz",
      "rozporiadzhennia",
      "postanova",
      "vysnovok",
    ]);
  });

  it("keeps threshold evaluation unavailable when the producer omits a decision score", () => {
    const packet = buildPublicDecisionPacket({
      decisionView,
      evidenceContext,
      governanceIssues: [],
      runId: "run-without-score",
    });

    expect(packet.thresholdContract).toMatchObject({
      aboveCount: null,
      belowCount: null,
      calibrationCaveat:
        "Decision threshold proximity is unavailable until a producer threshold contract is supplied.",
      edgeCases: [],
      epsilon: null,
      nearLineCount: null,
      threshold: null,
    });
  });

  it("does not mint a frontend threshold policy from a score and cohort deltas", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: testDecisionScore(0.82),
      decisionView,
      evidenceContext,
      governanceIssues: [],
      runId: "run-with-local-threshold-inputs",
    });

    expect(packet.thresholdContract).toMatchObject({
      aboveCount: null,
      belowCount: null,
      edgeCases: [],
      epsilon: null,
      nearLineCount: null,
      threshold: null,
    });
    expect(packet.thresholdContract.calibrationCaveat).toContain(
      "producer threshold contract",
    );
  });

  it("does not synthesize confidence or trust classifications from issue counts and artifact refs", () => {
    const withLocalSignals = buildPublicDecisionPacket({
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-neutral-publication",
    });
    const withoutLocalSignals = buildPublicDecisionPacket({
      decisionView,
      evidenceContext: null,
      governanceIssues: [],
      runId: "run-neutral-publication",
    });
    const producerAbsent = buildPublicDecisionPacket({
      decisionView: null,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-owner-confidence-absent",
    });
    const withTrustSignals = withLocalSignals.trustFraming as unknown as {
      integritySignatureNotice?: {
        authorityCaveat: string;
        signatureCue: string;
      };
      scenarioCaveats?: unknown;
    };
    const withoutTrustSignals = withoutLocalSignals.trustFraming as unknown as {
      integritySignatureNotice?: {
        authorityCaveat: string;
        signatureCue: string;
      };
      scenarioCaveats?: unknown;
    };

    expect(withLocalSignals.confidenceLadder).toEqual(
      withoutLocalSignals.confidenceLadder,
    );
    expect(
      JSON.stringify(
        withLocalSignals.confidenceLadder.map(({ label, reason, rung }) => ({
          label,
          reason,
          rung,
        })),
      ),
    ).not.toMatch(/weakest|disputed|untraced|low_confidence/u);
    expect(withTrustSignals.scenarioCaveats).toEqual([]);
    expect(withoutTrustSignals.scenarioCaveats).toEqual([]);
    expect(withTrustSignals.integritySignatureNotice).toEqual(
      withoutTrustSignals.integritySignatureNotice,
    );
    expect(withTrustSignals.integritySignatureNotice).toMatchObject({
      authorityCaveat:
        "This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority.",
      signatureCue: "frontend_integrity_signature_not_authoritative",
    });
    expect(producerAbsent.decision.confidence).toBeNull();
    expect(producerAbsent.confidenceLadder).toEqual([
      expect.objectContaining({
        label: "Owner confidence unavailable",
        rung: null,
        score: expect.objectContaining({ point: null }),
      }),
    ]);
  });

  it("signs and verifies immutable public packets without privileged context", () => {
    const signed = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(0.72),
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      runId: "run-35",
    });

    expect(signed.publicUrlPath).toMatch(/^\/public\/decisions\//u);
    expect(signed.signature).toMatch(/^sig:/u);
    expect(signed.projectionSemantics.primaryDisplayState.label).toBe(
      "projection_absent",
    );
    expect(signed.projectionSemantics.authorityRole).toBeNull();
    const verification = verifySignedPublicDecisionPacket(signed.signedId);
    expect(verification).toMatchObject({
      valid: true,
    });
    expect(verification.valid).toBe(true);
    if (!verification.valid) {
      throw new Error("expected a valid signed packet");
    }
    expect(
      isInteractionState(
        verification.packet.projectionSemantics.primaryDisplayState,
      ),
    ).toBe(true);
    expect(
      isInteractionState(verification.packet.coverageCaveat.caveatState),
    ).toBe(true);
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

  it("preserves an absent public decision metric as unknown instead of zero", () => {
    const packet = buildPublicDecisionPacket({
      decisionView: { ...decisionView, keyMetrics: [] },
      evidenceContext: null,
      governanceIssues: [],
      runId: "run-without-public-metric",
    });
    const [fallback] = packet.deterministicExplanations;

    expect(fallback?.quantity.point).toBeNull();
    expect(fallback?.narrative).toContain("Unknown");
    expect(fallback?.narrative).not.toContain("is 0.00");
  });

  it("preserves owner publishable state without minting closeout authority", () => {
    const projection = ownerProjection({
      may_not_be_used_for: ["owner_specific_use_limit"],
      primary_state: "publishable",
      states: ["publishable", "projection_only"],
    });
    const signed = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(0.72),
      decisionView,
      evidenceContext,
      governanceIssues: [issue()],
      policyDesignCaseProjection: projection,
      runId: "run-35",
    });

    expect(signed.projectionSemantics.primaryDisplayState.label).toBe(
      "publishable",
    );
    expect(signed.projectionSemantics.authorityRole).toBe("projection_only");
    expect(signed.projectionSemantics.closeoutTruth).toBe(
      projection.closeout_truth,
    );
    expect(signed.projectionSemantics.mayNotBeUsedFor).toContain(
      "owner_specific_use_limit",
    );
    expect(signed.projectionSemantics).not.toHaveProperty("primaryState");
  });

  it.each(opaqueProjectionStates)(
    "does not recompute closeout from opaque $caseId owner state",
    ({ label }) => {
      const projection = ownerProjection({
        primary_state: label,
        states: [label],
      });
      const signed = buildSignedPublicDecisionPacket({
        decisionScore: testDecisionScore(0.72),
        decisionView,
        evidenceContext,
        governanceIssues: [issue()],
        policyDesignCaseProjection: projection,
        runId: "run-35",
      });

      expect(signed.projectionSemantics.primaryDisplayState).toMatchObject({
        authorityPurpose: "candidate_display",
        label,
        purpose: "interaction_only",
      });
      expect(signed.projectionSemantics.closeoutTruth).toBe(
        projection.closeout_truth,
      );
      expect(signed.projectionSemantics).not.toHaveProperty("failClosedCodes");
      expect(signed.projectionSemantics).not.toHaveProperty("maskingCases");
    },
  );

  it("keeps private governance text out of the signed public model", () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: testDecisionScore(0.72),
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
      decisionScore: testDecisionScore(0.72),
      decisionView,
      evidenceContext,
      runId: "run-35",
    });

    expect(signPublicDecisionPacket(packet).signedId).toBe(
      signPublicDecisionPacket(packet).signedId,
    );
  });
});
