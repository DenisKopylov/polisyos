import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import {
  epochNonreceipt,
  type EpochSemantics,
} from "@/shared/ui/temporal/TimeSemanticsLabel";
import { renderWithProviders } from "@/test/render";
import type { PolicyDesignCaseProjection } from "@polisyos/runtime-api-client";

import {
  buildSignedPublicDecisionPacket as buildSignedPublicDecisionPacketRaw,
  type PublicDecisionPacketInput,
} from "../domain/publicationPacket";
import { PublicationPacketPanel } from "./PublicationPacketPanel";

type PacketTestInput = Omit<PublicDecisionPacketInput, "epochSemantics"> & {
  epochSemantics?: EpochSemantics;
};

function buildSignedPublicDecisionPacket(input: PacketTestInput) {
  return buildSignedPublicDecisionPacketRaw({
    ...input,
    epochSemantics: input.epochSemantics ?? epochNonreceipt(),
  });
}

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

function ownerProjection(primaryState: string): PolicyDesignCaseProjection {
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
    generated_at: "2026-05-19T10:00:00.000Z",
    may_not_be_used_for: ["scorecard_authority"],
    primary_state: primaryState,
    projection_policy: "reads_policy_design_case_only",
    provenance_kind: "runtime_projection",
    states: [primaryState],
    surface: "public_decision",
  };
}

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

describe("PublicationPacketPanel trust framing", () => {
  it("preserves a novel confidence label without minting a trust scenario", () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionView: {
        ...baseDecisionView,
        confidence: "future-owner-confidence",
      },
      evidenceContext: tracedEvidenceContext,
      runId: "opaque-confidence",
    });

    renderWithProviders(<PublicationPacketPanel packet={packet} publicMode />);

    expect(screen.getByText("future-owner-confidence")).toBeVisible();
    expect(
      screen.queryByTestId("trust-framing-low_confidence"),
    ).not.toBeInTheDocument();
    expect(packet.trustFraming.scenarioCaveats).toEqual([]);
  });

  it("renders an opaque owner projection state without a local trust scenario", () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      policyDesignCaseProjection: ownerProjection("future_owner_state"),
      runId: "opaque-owner-state",
    });

    renderWithProviders(<PublicationPacketPanel packet={packet} publicMode />);

    expect(
      screen.getByTestId("publication-projection-semantics"),
    ).toHaveTextContent("future_owner_state");
    expect(packet.trustFraming.scenarioCaveats).toEqual([]);
  });

  it("renders missing threshold evaluation as unavailable instead of measured zeros", () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionView: baseDecisionView,
      evidenceContext: tracedEvidenceContext,
      runId: "threshold-unavailable",
    });

    renderWithProviders(<PublicationPacketPanel packet={packet} publicMode />, {
      initialEntries: [packet.publicUrlPath],
    });

    const thresholdPanel = screen.getByTestId("threshold-contract-panel");

    expect(
      within(thresholdPanel).getByTestId("threshold-evaluation-unavailable"),
    ).toHaveTextContent("Unknown");
    expect(
      within(thresholdPanel).queryByTestId("threshold-near-count"),
    ).not.toBeInTheDocument();
    expect(
      within(thresholdPanel).queryByTestId("threshold-above-count"),
    ).not.toBeInTheDocument();
    expect(
      within(thresholdPanel).queryByTestId("threshold-below-count"),
    ).not.toBeInTheDocument();
  });

  it.each([
    {
      evidenceContext: tracedEvidenceContext,
      governanceIssues: [governanceIssue()],
      label: "issues-and-refs",
    },
    {
      evidenceContext: null,
      governanceIssues: [],
      label: "no-issues-or-refs",
    },
  ])(
    "renders only the non-authoritative integrity signature notice for $label",
    ({ evidenceContext, governanceIssues, label }) => {
      const packet = buildSignedPublicDecisionPacket({
        decisionView: baseDecisionView,
        evidenceContext,
        governanceIssues,
        runId: `integrity-framing-${label}`,
      });

      renderWithProviders(
        <PublicationPacketPanel packet={packet} publicMode />,
        {
          initialEntries: [packet.publicUrlPath],
        },
      );

      const caveats = screen.getByTestId("trust-framing-caveats");
      const integrityNotice = within(caveats).getByTestId(
        "frontend-integrity-signature-notice",
      );
      const integrityToken = screen.getByTestId(
        "frontend-integrity-signature-token",
      );

      expect(integrityNotice).toBeVisible();
      expect(integrityNotice).toHaveAttribute("data-kind", "neutral");
      expect(integrityNotice).toHaveTextContent(
        "This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority.",
      );
      expect(caveats).toHaveTextContent(
        "Frontend signatures, badges, labels, and projections are not closeout authority.",
      );
      expect(caveats).toHaveTextContent("runtime_closeout_authority");
      expect(caveats).not.toHaveTextContent(/closeout authority granted/i);
      expect(caveats).not.toHaveTextContent(/approval granted/i);
      expect(caveats).not.toHaveTextContent(/disputed|untraced/i);
      expect(integrityToken).toHaveAttribute("data-kind", "neutral");
      expect(integrityToken).toHaveAttribute(
        "title",
        "This frontend signature verifies packet integrity only; it is not trust, approval, publication, or closeout authority.",
      );
    },
  );

  it("renders threshold evaluation as unavailable without a producer contract", () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: untracedDecisionQuantity({
        metricId: "test.threshold-score",
        point: 0.72,
        reasonCode: "test_owner_score",
      }),
      decisionView: {
        ...baseDecisionView,
        distributional: {
          breakdowns: [
            {
              dimensionLabel: "Cohort",
              rows: [
                {
                  cohortLabel: "Near line",
                  direction: "negative",
                  isVulnerable: false,
                  populationShare: 0.5,
                  primaryDelta: -0.2,
                },
              ],
            },
          ],
          giniAfter: 0.3,
          giniBefore: 0.3,
          giniDelta: 0,
          losersCount: 0,
          losersShare: 0,
          vulnerableLosersCount: 0,
          winnersCount: 0,
          winnersShare: 0,
        },
      },
      runId: "neutral-threshold",
    });

    renderWithProviders(<PublicationPacketPanel packet={packet} publicMode />);

    const thresholdPanel = screen.getByTestId("threshold-contract-panel");
    expect(
      within(thresholdPanel).getByTestId("threshold-evaluation-unavailable"),
    ).toBeVisible();
    expect(
      within(thresholdPanel).queryByTestId("threshold-edge-case"),
    ).not.toBeInTheDocument();
    expect(thresholdPanel).toHaveTextContent("producer threshold contract");
  });
});
