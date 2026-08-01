import type {
  PolicyDesignCaseProjectionBlocker,
  ProjectionFreshness,
  QuantityUncertainty,
} from "@polisyos/runtime-api-client";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

import { DataFreshnessBadge } from "./DataFreshnessBadge";
import { EvidenceChain } from "./EvidenceChain";
import { ExplainabilityCard } from "./ExplainabilityCard";
import { MethodologyBadge } from "./MethodologyBadge";
import { NegativeCertificateCard } from "./NegativeCertificateCard";
import { ProvenanceChain } from "./ProvenanceChain";
import { ReasoningChainDisplay } from "./ReasoningChainDisplay";
import { TrustCalibrationDisplay } from "./TrustCalibrationDisplay";

const FRESHNESS: ProjectionFreshness = {
  basis: "source_timestamp",
  observed_at: "2026-07-22T11:00:00Z",
  source_as_of: "2026-07-22T10:00:00Z",
  state: "observed",
};

function percentQuantity(metricId: string, point: number | null) {
  return untracedDecisionQuantity({ metricId, point });
}

describe("compound authority bindings", () => {
  it("uses generated projection freshness without synthesizing cache age", () => {
    renderWithProviders(<DataFreshnessBadge freshness={FRESHNESS} />);

    const badge = screen.getByText("observed");
    expect(badge).toHaveAttribute("data-freshness-state", "observed");
    expect(badge).toHaveAttribute("data-source-as-of", "2026-07-22T10:00:00Z");
    expect(badge).not.toHaveAttribute("data-cache-age");
    expect(badge).not.toHaveTextContent(/ago|fresh|stale/i);
  });

  it("renders evidence references through the reference-only evidence primitive", () => {
    renderWithProviders(
      <EvidenceChain
        emptyBody="Nothing linked."
        emptyTitle="No evidence"
        items={[
          {
            artifactId: "artifact-1",
            evidenceRef: "evidence://claim/1",
            href: "/evidence/1",
            label: "Claim evidence",
          },
        ]}
        title="Evidence"
      />,
    );

    expect(screen.getByText("evidence://claim/1")).toHaveAttribute(
      "data-evidence-ref-value",
      "evidence://claim/1",
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "data-evidence-claim",
      "reference-only",
    );
  });

  it("keeps an owner decision grade explicit and unrecognized", () => {
    renderWithProviders(
      <ExplainabilityCard
        level="glance"
        verdict={{
          confidence: percentQuantity("decision.confidence", 0.84),
          decisionGrade: "future-owner-grade",
          summary: "Owner-provided summary",
        }}
      />,
    );

    expect(screen.getByText("future-owner-grade")).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(screen.getByTestId("quantity")).toHaveAttribute(
      "data-quantity-class",
      "decision",
    );
  });

  it("preserves generated methodology extensions opaquely", () => {
    const extension: QuantityUncertainty["method"] = "future-estimator";
    renderWithProviders(<MethodologyBadge methodology={extension} />);

    expect(screen.getByText("future-estimator")).toHaveAttribute(
      "data-methodology-owner-label",
      "future-estimator",
    );
  });

  it("renders the complete producer blocker without local severity mapping", () => {
    const blocker: PolicyDesignCaseProjectionBlocker = {
      code: "future_owner_blocker",
      evidence_ref: "evidence://blocker/1",
      message: "The producer stopped closeout.",
      module_id: "producer.module",
      next_action: "Collect verifier evidence",
      owner: "DS5 waist",
      severity: "future_severity",
    };

    renderWithProviders(<NegativeCertificateCard blocker={blocker} />);

    expect(screen.getByText("future_owner_blocker")).toBeInTheDocument();
    expect(screen.getByText("future_severity")).toHaveAttribute(
      "data-authority-presentation",
      "opaque",
    );
    expect(screen.getByText("DS5 waist")).toBeInTheDocument();
    expect(screen.getByText("Collect verifier evidence")).toBeInTheDocument();
    expect(screen.getByText("evidence://blocker/1")).toHaveAttribute(
      "data-evidence-ref-value",
      "evidence://blocker/1",
    );
  });

  it("reserves recorded provenance for generated lineage and marks derived summaries diagnostic", () => {
    renderWithProviders(
      <ProvenanceChain
        steps={[
          {
            evidenceRef: "evidence://lineage/1",
            href: "/evidence/lineage/1",
            lineage: {
              id: "lineage-1",
              kind: "artifact",
              label: "Generated lineage crumb",
            },
            source: "recorded-lineage",
          },
          {
            diagnosticLabel: "future_summary_state",
            id: "summary-1",
            label: "Derived run summary",
            source: "diagnostic-summary",
            type: "result",
          },
        ]}
      />,
    );

    expect(screen.getByText("Generated lineage crumb")).toHaveAttribute(
      "data-provenance-source",
      "recorded-lineage",
    );
    expect(screen.getByText("Derived run summary")).toHaveAttribute(
      "data-provenance-source",
      "diagnostic-summary",
    );
    expect(screen.getByText("future_summary_state")).toHaveAttribute(
      "data-authority-presentation",
      "diagnostic",
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "data-evidence-claim",
      "reference-only",
    );
  });

  it("clothes model reasoning as candidate material", () => {
    renderWithProviders(
      <ReasoningChainDisplay
        steps={[
          {
            id: "reasoning-1",
            summary: "Model-authored rationale",
            title: "Suggested conclusion",
            type: "conclusion",
          },
        ]}
      />,
    );

    expect(screen.getByTestId("reasoning-chain")).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    expect(screen.getByText("Candidate reasoning")).toBeInTheDocument();
  });

  it("renders trust percentages as generated quantities without recalibrating them", () => {
    renderWithProviders(
      <TrustCalibrationDisplay
        calibrationRecords={[
          {
            actualCoverage: percentQuantity("coverage.actual", 0.73),
            expectedCoverage: percentQuantity("coverage.expected", 0.8),
            level: percentQuantity("coverage.level", 0.8),
          },
        ]}
        historicalAccuracy={percentQuantity("trust.accuracy", null)}
        methodology="future-estimator"
        totalPastAnalyses={12}
      />,
    );

    expect(screen.getByText("Unknown")).toBeVisible();
    expect(screen.getByText("73%")).toBeVisible();
    expect(screen.getAllByText("80%")).toHaveLength(2);
    for (const quantity of screen.getAllByTestId("quantity")) {
      expect(quantity).toHaveAttribute("data-quantity-class", "decision");
    }
  });
});
