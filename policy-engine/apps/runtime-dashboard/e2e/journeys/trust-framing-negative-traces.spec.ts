import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";

import {
  buildSignedPublicDecisionPacket,
  type PublicDecisionPacketInput,
} from "../../src/features/runs/domain/publicationPacket";

const specDir = path.dirname(fileURLToPath(import.meta.url));
const policyEngineRoot = path.resolve(specDir, "../../../..");
const screenshotDir = path.resolve(
  policyEngineRoot,
  "_build/policy-design-case/rebaseline/wave-35G/trust-framing-ui-negative-traces",
);

const baseDecisionView: DecisionCardViewModel = {
  confidence: "HIGH",
  diagnosticsBadges: [],
  distributional: null,
  generatedAt: "2026-05-19T10:00:00.000Z",
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
      name: "Outcome",
      unit: "%",
      value: 1.2,
    },
  ],
  metricComparisons: [],
  metricValidationFamilyAdjustment: null,
  policySummary: "Approve with published safeguards.",
  runId: "trust-framing-run",
  sourceKind: "decision_packet",
  totalDurationMs: 1200,
  verdict: "APPROVE",
};

const tracedEvidenceContext: RunEvidenceContext = {
  dataNeeds: [],
  dataSnapshotRef: {
    artifact_id: "snapshot-traced",
    kind: "data_snapshot",
  },
  evidenceBundleRef: {
    artifact_id: "bundle-traced",
    kind: "evidence_bundle",
  },
  executionPlanRef: null,
  fetchPlans: [],
  inputBindingsRef: {
    artifact_id: "bindings-traced",
    kind: "input_bindings",
  },
  promotionCandidates: [],
  relatedArtifacts: [],
  runId: "trust-framing-run",
  sourceKind: "core_run",
  warnings: [],
};

function governanceIssue(): GovernanceIssueView {
  return {
    code: "public_rebuttal",
    durationMs: 10,
    message: "Public rebuttal remains open.",
    passId: "governance-pass",
    path: null,
    raw: {},
    severity: "warning",
  };
}

const trustFramingCases = [
  {
    scenario: "low_confidence",
    input: {
      decisionView: { ...baseDecisionView, confidence: "LOW" },
      evidenceContext: tracedEvidenceContext,
    },
  },
  {
    scenario: "disputed",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      governanceIssues: [governanceIssue()],
    },
  },
  {
    scenario: "untraced",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: null,
    },
  },
  {
    scenario: "simulated",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      policyDesignCaseProjection: {
        labels: [
          { label: "simulated research profile", state: "projection_only" },
        ],
        primary_state: "projection_only",
        states: ["projection_only"],
      },
    },
  },
  {
    scenario: "stale",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      policyDesignCaseProjection: {
        labels: [{ label: "stale", state: "stale" }],
        primary_state: "stale",
        states: ["stale", "projection_only"],
      },
    },
  },
  {
    scenario: "draft",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      policyDesignCaseProjection: {
        labels: [{ label: "draft", state: "draft" }],
        primary_state: "draft",
        states: ["draft", "projection_only"],
      },
    },
  },
  {
    scenario: "override_approved",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      policyDesignCaseProjection: {
        labels: [{ label: "override-approved", state: "projection_only" }],
        primary_state: "projection_only",
        states: ["projection_only"],
      },
    },
  },
  {
    scenario: "frontend_signed",
    input: {
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
    },
  },
] satisfies {
  input: Omit<PublicDecisionPacketInput, "runId">;
  scenario: string;
}[];

test.describe("Wave 35G trust-framing negative UI traces", () => {
  test.beforeAll(async () => {
    await mkdir(screenshotDir, { recursive: true });
  });

  for (const { input, scenario } of trustFramingCases) {
    test(`captures trust-framing-${scenario}`, async ({ page }) => {
      const packet = buildSignedPublicDecisionPacket({
        ...input,
        runId: `trust-framing-${scenario}`,
      });

      await page.goto(packet.publicUrlPath);

      const caveats = page.getByTestId("trust-framing-caveats");
      await expect(caveats).toBeVisible();
      await expect(
        caveats.getByTestId(`trust-framing-${scenario}`),
      ).toBeVisible();
      await expect(caveats).toContainText(
        "Use runtime scorecard/readiness authority before approval or closeout.",
      );
      await expect(caveats).toContainText(
        "Frontend signatures, badges, labels, and projections are not closeout authority.",
      );
      await expect(caveats).toContainText("runtime_closeout_authority");
      await expect(caveats).not.toContainText(/closeout authority granted/i);
      await expect(caveats).not.toContainText(/approval granted/i);

      await caveats.screenshot({
        path: path.join(screenshotDir, `${scenario}.png`),
      });
    });
  }
});
