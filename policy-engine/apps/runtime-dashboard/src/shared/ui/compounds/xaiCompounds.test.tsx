/**
 * Tests for the 11 XAI compound components used in RunExplainabilityPanel.
 *
 * Chart primitives (ConfidenceGauge, WaterfallChart, RadarChart, AnimatedProgress,
 * ChartDataTable) are mocked to keep tests focused on component logic and rendering.
 */

vi.mock("@/shared/charts", () => ({
  ConfidenceGauge: ({ value, label }: { value: number; label?: string }) => (
    <div data-testid="confidence-gauge">
      {label && <span>{label}</span>}
      <span>{Math.round(value * 100)}%</span>
    </div>
  ),
  WaterfallChart: ({ steps }: { steps: unknown[] }) => (
    <div data-testid="waterfall-chart">{steps.length} steps</div>
  ),
  RadarChart: ({ series }: { series: unknown[] }) => (
    <div data-testid="radar-chart">{series.length} series</div>
  ),
  AnimatedProgress: ({ value }: { value: number }) => (
    <div
      data-testid="animated-progress"
      role="progressbar"
      aria-valuenow={value}
    />
  ),
}));

vi.mock("@/shared/charts/theme", () => ({
  chartTheme: {
    primary: "#1c8b82",
    secondary: "#2557a7",
    success: "#12805c",
    alert: "#cb5a2e",
    warning: "#7f9f2f",
    neutral: "#40515f",
    axis: "rgba(64,81,95,0.9)",
  },
  chartDefaults: { tickFontSize: 11 },
}));

vi.mock("@/shared/charts/accessibility", () => ({
  ChartDataTable: ({ caption }: { caption: string }) => (
    <table data-testid="chart-data-table">
      <caption>{caption}</caption>
    </table>
  ),
}));

import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

import { ExplainabilityCard } from "./ExplainabilityCard";
import { GovernancePassGrid } from "./GovernancePassGrid";
import { AttributionWaterfall } from "./AttributionWaterfall";
import { TrustCalibrationDisplay } from "./TrustCalibrationDisplay";
import { EvidenceCoverageRadar } from "./EvidenceCoverageRadar";
import { SensitivityPlot } from "./SensitivityPlot";
import { FactorImportanceChart } from "./FactorImportanceChart";
import { ReasoningChainDisplay } from "./ReasoningChainDisplay";
import { NegativeCertificateCard } from "./NegativeCertificateCard";
import { ProvenanceChain } from "./ProvenanceChain";
import { MethodologyBadge } from "./MethodologyBadge";

// ---------------------------------------------------------------------------
// 1. ExplainabilityCard
// ---------------------------------------------------------------------------
describe("ExplainabilityCard", () => {
  const baseVerdict = {
    status: "approved" as const,
    confidence: 0.92,
    summary: "Strong evidence",
  };

  it("renders glance level with verdict and confidence", () => {
    renderWithProviders(<ExplainabilityCard verdict={baseVerdict} />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("Strong evidence")).toBeInTheDocument();
  });

  it("shows key factors at summary level", () => {
    renderWithProviders(
      <ExplainabilityCard
        verdict={baseVerdict}
        level="summary"
        keyFactors={[
          { label: "Sample size", value: "4200", direction: "positive" },
          { label: "Bias risk", value: "low", direction: "neutral" },
        ]}
      />,
    );
    expect(screen.getByText("Sample size")).toBeInTheDocument();
    expect(screen.getByText("4200")).toBeInTheDocument();
    expect(screen.getByText("Bias risk")).toBeInTheDocument();
  });

  it("shows governance blockers at summary level", () => {
    renderWithProviders(
      <ExplainabilityCard
        verdict={baseVerdict}
        level="summary"
        governance={{
          passed: 3,
          failed: 1,
          warnings: 0,
          blockers: ["Missing consent"],
        }}
      />,
    );
    expect(screen.getByText("Governance blockers")).toBeInTheDocument();
    expect(screen.getByText("Missing consent")).toBeInTheDocument();
  });

  it("expands from glance to summary via button", () => {
    renderWithProviders(
      <ExplainabilityCard
        verdict={baseVerdict}
        expandTo="summary"
        keyFactors={[{ label: "Effect", value: "0.35", direction: "positive" }]}
      />,
    );
    expect(screen.queryByText("Effect")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByText("Effect")).toBeInTheDocument();
  });

  it("renders methodology label", () => {
    renderWithProviders(
      <ExplainabilityCard verdict={baseVerdict} methodology="DiD" />,
    );
    expect(screen.getByText("DiD")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. GovernancePassGrid
// ---------------------------------------------------------------------------
describe("GovernancePassGrid", () => {
  const passes = [
    { id: "g1", label: "Data quality", status: "pass" as const },
    {
      id: "g2",
      label: "Legal review",
      status: "fail" as const,
      detail: "GDPR concern",
    },
    {
      id: "g3",
      label: "Ethics check",
      status: "warning" as const,
      durationMs: 120,
    },
    { id: "g4", label: "Deferred", status: "skip" as const },
  ];

  it("renders all pass tiles with correct aria-labels", () => {
    renderWithProviders(<GovernancePassGrid passes={passes} />);
    expect(screen.getByLabelText("Data quality: Passed")).toBeInTheDocument();
    expect(screen.getByLabelText("Legal review: Failed")).toBeInTheDocument();
    expect(screen.getByLabelText("Ethics check: Warning")).toBeInTheDocument();
    expect(screen.getByLabelText("Deferred: Skipped")).toBeInTheDocument();
  });

  it("shows count summary", () => {
    renderWithProviders(<GovernancePassGrid passes={passes} />);
    expect(screen.getByText("Passed: 1")).toBeInTheDocument();
    expect(screen.getByText("Failed: 1")).toBeInTheDocument();
    expect(screen.getByText("Warning: 1")).toBeInTheDocument();
    expect(screen.getByText("Skipped: 1")).toBeInTheDocument();
  });

  it("renders custom title", () => {
    renderWithProviders(
      <GovernancePassGrid passes={passes} title="Compliance Gates" />,
    );
    expect(screen.getByText("Compliance Gates")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. AttributionWaterfall
// ---------------------------------------------------------------------------
describe("AttributionWaterfall", () => {
  it("renders base, contributions, and final total", () => {
    renderWithProviders(
      <AttributionWaterfall
        baseValue={untracedDecisionQuantity({
          metricId: "test.attribution_baseline",
          point: 0.5,
        })}
        contributions={[
          { label: "Education", value: 0.12 },
          { label: "Income", value: -0.03 },
        ]}
      />,
    );
    expect(screen.getByText("Base prediction")).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
    expect(screen.getByText("Income")).toBeInTheDocument();
    expect(screen.getByText("Final estimate")).toBeInTheDocument();
    // Final value = 0.5 + 0.12 - 0.03 = 0.59
    expect(screen.getByText("0.5900")).toBeInTheDocument();
  });

  it("renders the waterfall chart", () => {
    renderWithProviders(
      <AttributionWaterfall
        baseValue={untracedDecisionQuantity({
          metricId: "test.attribution_baseline",
          point: 1,
        })}
        contributions={[{ label: "A", value: 0.1 }]}
      />,
    );
    expect(screen.getByTestId("waterfall-chart")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. TrustCalibrationDisplay
// ---------------------------------------------------------------------------
describe("TrustCalibrationDisplay", () => {
  it("renders accuracy and methodology", () => {
    renderWithProviders(
      <TrustCalibrationDisplay
        methodology="DiD"
        historicalAccuracy={0.87}
        totalPastAnalyses={42}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Trust calibration" }),
    ).toBeInTheDocument();
    // "87%" appears in both gauge mock and body text
    expect(screen.getAllByText("87%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/42 historical analyses/)).toBeInTheDocument();
  });

  it("renders limitations and counter-arguments", () => {
    renderWithProviders(
      <TrustCalibrationDisplay
        methodology="SC"
        historicalAccuracy={0.72}
        totalPastAnalyses={10}
        limitations={["Small sample"]}
        counterArguments={["Selection bias possible"]}
      />,
    );
    expect(screen.getByText("Known limitations")).toBeInTheDocument();
    expect(screen.getByText("Small sample")).toBeInTheDocument();
    expect(
      screen.getByText("Why you should NOT trust this"),
    ).toBeInTheDocument();
    expect(screen.getByText("Selection bias possible")).toBeInTheDocument();
  });

  it("renders calibration records", () => {
    renderWithProviders(
      <TrustCalibrationDisplay
        methodology="DiD"
        historicalAccuracy={0.9}
        totalPastAnalyses={50}
        calibrationRecords={[
          { level: 0.95, expectedCoverage: 0.95, actualCoverage: 0.93 },
        ]}
      />,
    );
    expect(screen.getByText("Calibration check")).toBeInTheDocument();
    expect(screen.getByText("95% CI")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5. EvidenceCoverageRadar
// ---------------------------------------------------------------------------
describe("EvidenceCoverageRadar", () => {
  const coverage = { academic: 0.8, dataset: 0.6, legal: 0.9, transport: 0.4 };

  it("renders dimension values and overall", () => {
    renderWithProviders(<EvidenceCoverageRadar coverage={coverage} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    // Overall = (0.8+0.6+0.9+0.4)/4 = 0.675 → 68%
    expect(screen.getByText("Overall: 68%")).toBeInTheDocument();
  });

  it("renders radar chart with benchmark series", () => {
    renderWithProviders(
      <EvidenceCoverageRadar
        coverage={coverage}
        benchmark={{ academic: 0.9, dataset: 0.9, legal: 0.9, transport: 0.9 }}
      />,
    );
    expect(screen.getByTestId("radar-chart")).toHaveTextContent("2 series");
  });
});

// ---------------------------------------------------------------------------
// 6. SensitivityPlot
// ---------------------------------------------------------------------------
describe("SensitivityPlot", () => {
  const points = [
    { gamma: 1.0, upperBound: 0.5, lowerBound: 0.3 },
    { gamma: 1.5, upperBound: 0.6, lowerBound: 0.1 },
    { gamma: 2.0, upperBound: 0.7, lowerBound: -0.05 },
  ];

  it("renders title and data table", () => {
    renderWithProviders(<SensitivityPlot points={points} />);
    expect(
      screen.getByRole("heading", {
        name: "Sensitivity Analysis (Rosenbaum Bounds)",
      }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("chart-data-table")).toBeInTheDocument();
  });

  it("shows breakdown gamma label", () => {
    renderWithProviders(
      <SensitivityPlot points={points} breakdownGamma={1.5} />,
    );
    expect(screen.getByText("Robust up to \u0393=1.5")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 7. FactorImportanceChart
// ---------------------------------------------------------------------------
describe("FactorImportanceChart", () => {
  const factors = [
    { label: "Age", importance: 0.35, direction: "positive" as const },
    { label: "Region", importance: -0.12, direction: "negative" as const },
    { label: "Gender", importance: 0.02, direction: "neutral" as const },
  ];

  it("renders chart with data table", () => {
    renderWithProviders(<FactorImportanceChart factors={factors} />);
    expect(
      screen.getByRole("heading", { name: "Factor Importance" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("chart-data-table")).toBeInTheDocument();
  });

  it("respects maxBars limit", () => {
    renderWithProviders(
      <FactorImportanceChart factors={factors} maxBars={2} />,
    );
    expect(screen.getByText("Age")).toBeInTheDocument();
    expect(screen.getByText("Region")).toBeInTheDocument();
    expect(screen.queryByText("Gender")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 8. ReasoningChainDisplay
// ---------------------------------------------------------------------------
describe("ReasoningChainDisplay", () => {
  const steps = [
    {
      id: "s1",
      type: "question" as const,
      title: "User asked",
      summary: "What is the effect?",
    },
    {
      id: "s2",
      type: "analysis" as const,
      title: "Ran DiD",
      summary: "Parallel trends hold",
      durationMs: 230,
    },
    {
      id: "s3",
      type: "conclusion" as const,
      title: "Positive effect",
      summary: "ATE = 0.42",
    },
  ];

  it("renders all steps with correct labels", () => {
    renderWithProviders(<ReasoningChainDisplay steps={steps} />);
    expect(screen.getByText("User question")).toBeInTheDocument();
    expect(screen.getByText("Causal analysis")).toBeInTheDocument();
    expect(screen.getByText("Conclusion")).toBeInTheDocument();
    expect(screen.getByText("User asked")).toBeInTheDocument();
    expect(screen.getByText("230ms")).toBeInTheDocument();
  });

  it("toggles step detail on click", () => {
    renderWithProviders(
      <ReasoningChainDisplay
        steps={[
          {
            id: "d1",
            type: "analysis" as const,
            title: "Step",
            summary: "Sum",
            detail: "Extra info",
          },
        ]}
      />,
    );
    expect(screen.queryByText("Extra info")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByText("Extra info")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Hide details"));
    expect(screen.queryByText("Extra info")).not.toBeInTheDocument();
  });

  it("expand/collapse all", () => {
    renderWithProviders(
      <ReasoningChainDisplay
        steps={[
          {
            id: "e1",
            type: "question" as const,
            title: "Q",
            summary: "S",
            detail: "Detail A",
          },
          {
            id: "e2",
            type: "conclusion" as const,
            title: "C",
            summary: "S",
            detail: "Detail B",
          },
        ]}
      />,
    );
    fireEvent.click(screen.getByText("Expand all"));
    expect(screen.getByText("Detail A")).toBeInTheDocument();
    expect(screen.getByText("Detail B")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Collapse all"));
    expect(screen.queryByText("Detail A")).not.toBeInTheDocument();
  });

  it("shows total duration", () => {
    renderWithProviders(<ReasoningChainDisplay steps={steps} />);
    expect(screen.getByText("Total: 230ms")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 9. NegativeCertificateCard
// ---------------------------------------------------------------------------
describe("NegativeCertificateCard", () => {
  it("renders blocking type badge and reason", () => {
    renderWithProviders(
      <NegativeCertificateCard
        blockingType="identification_failure"
        reason="Cannot identify causal effect"
      />,
    );
    expect(screen.getByText("Not identified")).toBeInTheDocument();
    expect(
      screen.getByText("Cannot identify causal effect"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Why a precise answer is unavailable"),
    ).toBeInTheDocument();
  });

  it("renders violated assumptions", () => {
    renderWithProviders(
      <NegativeCertificateCard
        blockingType="assumption_violation"
        reason="Failed"
        assumptions={["Parallel trends", "No spillover"]}
      />,
    );
    expect(screen.getByText("Violated assumptions")).toBeInTheDocument();
    expect(screen.getByText("Parallel trends")).toBeInTheDocument();
    expect(screen.getByText("No spillover")).toBeInTheDocument();
  });

  it("renders suggested experiments with feasibility", () => {
    renderWithProviders(
      <NegativeCertificateCard
        blockingType="data_insufficient"
        reason="Need more data"
        suggestedExperiments={[
          {
            id: "exp1",
            description: "Run RCT",
            rationale: "Gold standard",
            feasibility: "high",
          },
        ]}
      />,
    );
    expect(screen.getByText("Suggested experiments")).toBeInTheDocument();
    expect(screen.getByText("Run RCT")).toBeInTheDocument();
    expect(screen.getByText("Gold standard")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("handles unknown blocking types gracefully", () => {
    renderWithProviders(
      <NegativeCertificateCard
        blockingType="custom_block"
        reason="Unknown reason"
      />,
    );
    expect(screen.getByText("custom_block")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 10. ProvenanceChain
// ---------------------------------------------------------------------------
describe("ProvenanceChain", () => {
  const steps = [
    {
      id: "p1",
      label: "Input dataset",
      type: "data" as const,
      detail: "v2.3",
      timestamp: "2026-03-10",
    },
    {
      id: "p2",
      label: "DiD estimation",
      type: "method" as const,
      statusLabel: "Completed",
      status: "ok" as const,
    },
    {
      id: "p3",
      label: "ATE result",
      type: "result" as const,
      href: "/artifacts/result-1",
    },
    { id: "p4", label: "Compliance gate", type: "governance" as const },
  ];

  it("renders all provenance steps", () => {
    renderWithProviders(<ProvenanceChain steps={steps} />);
    expect(screen.getByText("Input dataset")).toBeInTheDocument();
    expect(screen.getByText("DiD estimation")).toBeInTheDocument();
    expect(screen.getByText("ATE result")).toBeInTheDocument();
    expect(screen.getByText("Compliance gate")).toBeInTheDocument();
  });

  it("renders detail, timestamp, and status badge", () => {
    renderWithProviders(<ProvenanceChain steps={steps} />);
    expect(screen.getByText("v2.3")).toBeInTheDocument();
    expect(screen.getByText("2026-03-10")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("renders View link when href provided", () => {
    renderWithProviders(<ProvenanceChain steps={steps} />);
    const viewLinks = screen.getAllByText("View");
    expect(viewLinks.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 11. MethodologyBadge
// ---------------------------------------------------------------------------
describe("MethodologyBadge", () => {
  it("renders known methodology abbreviation", () => {
    renderWithProviders(<MethodologyBadge methodology="did" />);
    expect(screen.getByText("DiD")).toBeInTheDocument();
  });

  it("renders unknown methodology as-is", () => {
    renderWithProviders(<MethodologyBadge methodology="custom_method" />);
    expect(screen.getByText("custom_method")).toBeInTheDocument();
  });

  it("renders all known methodologies", () => {
    const known = [
      "did",
      "sc",
      "tmle",
      "dml",
      "iv",
      "rdd",
      "bsts",
      "meta_learner",
      "ols",
    ];
    const shorts = [
      "DiD",
      "SC",
      "TMLE",
      "DML",
      "IV",
      "RDD",
      "BSTS",
      "Meta-L",
      "OLS",
    ];

    known.forEach((key, i) => {
      const { unmount } = renderWithProviders(
        <MethodologyBadge methodology={key} />,
      );
      expect(screen.getByText(shorts[i])).toBeInTheDocument();
      unmount();
    });
  });
});
