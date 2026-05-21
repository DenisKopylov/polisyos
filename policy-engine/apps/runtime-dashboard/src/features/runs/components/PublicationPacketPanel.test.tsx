import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import { renderWithProviders } from "@/test/render";

import {
  buildSignedPublicDecisionPacket,
  type PublicDecisionPacketInput,
} from "../domain/publicationPacket";
import { PublicationPacketPanel } from "./PublicationPacketPanel";

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

describe("PublicationPacketPanel trust framing", () => {
  it.each(trustFramingCases)(
    "renders a visible non-authority caveat for $scenario",
    ({ input, scenario }) => {
      const packet = buildSignedPublicDecisionPacket({
        ...input,
        runId: `trust-framing-${scenario}`,
      });

      renderWithProviders(
        <PublicationPacketPanel packet={packet} publicMode />,
        {
          initialEntries: [packet.publicUrlPath],
        },
      );

      const caveats = screen.getByTestId("trust-framing-caveats");
      const scenarioRow = within(caveats).getByTestId(
        `trust-framing-${scenario}`,
      );

      expect(scenarioRow).toBeVisible();
      expect(scenarioRow).toHaveTextContent(
        "Use runtime scorecard/readiness authority before approval or closeout.",
      );
      expect(caveats).toHaveTextContent(
        "Frontend signatures, badges, labels, and projections are not closeout authority.",
      );
      expect(caveats).toHaveTextContent("runtime_closeout_authority");
      expect(caveats).not.toHaveTextContent(/closeout authority granted/i);
      expect(caveats).not.toHaveTextContent(/approval granted/i);
    },
  );
});
