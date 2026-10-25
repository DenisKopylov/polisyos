import { screen, within } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import {
  legacyLimitedProjection,
  pointSummary,
} from "../domain/__test__/decisionPacketHteFixtures";

vi.mock("@/shared/charts", () => ({
  UncertaintyBand: ({ identifiability }: { identifiability: string }) => (
    <div
      data-identifiability={identifiability}
      data-testid="decision-metric-uncertainty"
    />
  ),
}));

import DecisionCardView from "./DecisionCardView";

function decisionPacketWithHTE(hte: unknown) {
  return {
    feedback: { issues: [], verdict: "review" },
    simulation_results: { gdp_change: 0.12 },
    run_id: "run-hte-route",
    hte,
  };
}

describe("DecisionCardView", () => {
  it("renders the producer identifiability member without inferring from warnings", () => {
    const view = renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={{
          feedback: { issues: [], verdict: "review" },
          metric_significance: {
            gdp_change: {
              effect_size: {
                identifiability: "assumed",
                point: 0.12,
              },
            },
          },
          simulation_results: { gdp_change: 0.12 },
          uncertainty_bounds: {
            gdp_change_ci_level: 0.95,
            gdp_change_lower: 0.1,
            gdp_change_upper: 0.14,
          },
        }}
      />,
    );

    expect(screen.getByTestId("decision-metric-uncertainty")).toHaveAttribute(
      "data-identifiability",
      "assumed",
    );

    view.unmount();
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={{
          feedback: { issues: [], verdict: "review" },
          metric_significance: {
            gdp_change: {
              assumption_warnings: ["unverified extension"],
              effect_size: {
                identifiability: "novel_owner_extension",
                point: 0.12,
              },
            },
          },
          simulation_results: { gdp_change: 0.12 },
          uncertainty_bounds: {
            gdp_change_lower: 0.1,
            gdp_change_upper: 0.14,
          },
        }}
      />,
    );
    expect(screen.getByTestId("decision-metric-uncertainty")).toHaveAttribute(
      "data-identifiability",
      "unknown",
    );
  });

  it("renders the typed HTE projection and all direct evidence refs on the default card", () => {
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={decisionPacketWithHTE(pointSummary())}
      />,
    );

    expect(screen.getByTestId("hte-outcome")).toHaveAttribute(
      "data-hte-outcome-kind",
      "point_estimate",
    );
    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.25",
    );
    expect(
      screen
        .getAllByRole("link")
        .find((link) => link.getAttribute("href")?.includes("ir.hte_outcome")),
    ).toHaveAttribute("href", expect.stringContaining("ir.hte_outcome"));
    expect(screen.getByTestId("hte-outcome")).toHaveTextContent(
      "Not established",
    );
  });

  it("renders the same typed HTE projection inside the reading and print target", () => {
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={decisionPacketWithHTE(pointSummary())}
        viewMode="reading"
      />,
    );

    expect(screen.getByTestId("hte-outcome")).toHaveAttribute(
      "data-hte-outcome-kind",
      "point_estimate",
    );
    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.25",
    );
    expect(
      screen
        .getAllByRole("link")
        .find((link) => link.getAttribute("href")?.includes("ir.hte_outcome")),
    ).toHaveAttribute("href", expect.stringContaining("ir.hte_outcome"));
    const printTarget = screen.getByTestId("decision-packet-print-target");
    expect(printTarget).toHaveAttribute(
      "id",
      "decision-packet-viewer-run-hte-route",
    );
    expect(within(printTarget).getByTestId("hte-outcome")).toBeVisible();
  });

  it("does not interpret an HTE-shaped payload on a different artifact route", () => {
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.other_artifact"
        payload={decisionPacketWithHTE(pointSummary())}
      />,
    );

    expect(screen.queryByTestId("hte-outcome")).not.toBeInTheDocument();
    expect(screen.queryByTestId("hte-outcome-invalid")).not.toBeInTheDocument();
  });

  it("keeps a present malformed HTE summary visible as invalid on the reading and print route", () => {
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={decisionPacketWithHTE(null)}
        viewMode="reading"
      />,
    );

    expect(screen.getByTestId("hte-outcome-invalid")).toBeInTheDocument();
    expect(screen.getByRole("article")).toBeInTheDocument();
  });

  it("carries the legacy limited sidecar through reading and print without a result link", () => {
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        viewMode="reading"
        payload={{
          feedback: { issues: [], verdict: "review" },
          simulation_results: { gdp_change: 0.12 },
          run_id: "run-hte-legacy",
          hte: null,
          hte_projection_status: "legacy_limited",
          hte_legacy_limited: legacyLimitedProjection(),
        }}
      />,
    );

    const printTarget = screen.getByTestId("decision-packet-print-target");
    const outcomes = screen.getAllByTestId("hte-outcome");
    expect(outcomes).toHaveLength(1);
    expect(within(printTarget).getByTestId("hte-outcome")).toBe(outcomes[0]);
    for (const outcome of outcomes) {
      expect(outcome).toHaveAttribute(
        "data-hte-outcome-kind",
        "legacy_limited",
      );
      expect(outcome).toHaveTextContent("0.25");
      expect(within(outcome).queryByRole("link")).not.toBeInTheDocument();
    }
  });
});
