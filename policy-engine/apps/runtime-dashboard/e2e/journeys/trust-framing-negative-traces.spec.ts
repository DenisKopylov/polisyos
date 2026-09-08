import { forgeLegacyPublicDecisionUrl } from "../../src/test/forgeLegacyPublicDecisionUrl";
import { epochNonreceipt } from "../../src/shared/lib/domain/epochSemantics";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";

import {
  buildPublicDecisionPacket,
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
  input: Omit<PublicDecisionPacketInput, "runId" | "epochSemantics">;
  scenario: string;
}[];

test.describe("Wave 35G trust-framing negative UI traces", () => {
  test.beforeAll(async () => {
    await mkdir(screenshotDir, { recursive: true });
  });

  for (const { input, scenario } of trustFramingCases) {
    test(`captures trust-framing-${scenario}`, async ({ page }) => {
      const packet = buildPublicDecisionPacket({
        ...input,
        epochSemantics: epochNonreceipt(),
        runId: `trust-framing-${scenario}`,
      });

      const forgedUrl = forgeLegacyPublicDecisionUrl(packet);
      const recordId = forgedUrl.split("/").at(-1);
      const verifierResponse = page
        .waitForEvent("requestfinished", (request) => {
          const url = new URL(request.url());
          return (
            url.pathname === "/api/v1/public-decisions/verification" &&
            url.searchParams.get("record_id") === recordId
          );
        })
        .then(async (request) => {
          const response = await request.response();
          if (!response) throw new Error("verification_response_missing");
          return response;
        });
      await page.goto(forgedUrl);
      const serverVerdict = await (await verifierResponse).json();
      expect(serverVerdict.record_id).toBe(recordId);
      expect(serverVerdict.report_authentication).toBe("invalid");
      expect(serverVerdict.reason_codes).toContain(
        "client_token_not_server_issued",
      );

      const caveats = page.getByTestId("public-decision-unavailable");
      await expect(caveats).toBeVisible();
      await expect(caveats).toContainText("client_token_not_server_issued");
      await expect(page.getByTestId("publication-packet-panel")).toHaveCount(0);
      await expect(
        page.getByText("signature verified", { exact: true }),
      ).toHaveCount(0);
      await expect(caveats).not.toContainText(/closeout authority granted/i);
      await expect(caveats).not.toContainText(/approval granted/i);

      await caveats.screenshot({
        path: path.join(screenshotDir, `${scenario}.png`),
      });
    });
  }
});
