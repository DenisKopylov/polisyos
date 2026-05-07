import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";

import { CounterfactualQuantity } from "./CounterfactualQuantity";
import type { CounterfactualMetric, QuantityValue } from "./quantity.types";

describe("CounterfactualQuantity", () => {
  it("renders actual, scenario and delta values with ScenarioRef", () => {
    renderWithProviders(<CounterfactualQuantity value={metric} />, {
      interactiveProviders: true,
    });

    expect(screen.getByText("Actual")).toBeInTheDocument();
    expect(screen.getByText("Scenario")).toBeInTheDocument();
    expect(screen.getByText("Delta")).toBeInTheDocument();
    expect(screen.getAllByTestId("quantity")[0]).toHaveAttribute(
      "data-lineage-status",
      "verified",
    );
    expect(
      screen.getByLabelText(
        "Employment: actual and scenario values for scn_fixture",
      ),
    ).toHaveAttribute("data-scenario-id", "scn_fixture");
  });
});

const baseLineage = {
  id: "lineage:employment",
  status: "verified",
  freshness: "current",
  summary: { source: "test" },
} as const;

const actual: QuantityValue = {
  point: 0.2,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "employment_rate_delta",
  label: "Employment",
  lineage: baseLineage,
  time: { valid_at: "2026-04-15T12:00:00Z" },
  quantity_class: "decision",
};

const scenario: QuantityValue = {
  ...actual,
  point: 0.23,
  metric_id: "employment_rate_delta.counterfactual",
  lineage: {
    id: "scenario:scn_fixture:projection",
    status: "pending",
    freshness: "current",
    summary: { source: "scenario", assumptions: "asm_1" },
  },
  time: { ...actual.time, scenario_id: "scn_fixture" },
};

const metric: CounterfactualMetric = {
  metric_id: "employment_rate_delta",
  label: "Employment",
  actual,
  counterfactual: scenario,
  delta: {
    ...scenario,
    point: 0.03,
    metric_id: "employment_rate_delta.counterfactual_delta",
    label: "Employment delta",
  },
  scenario_ref: {
    id: "scn_fixture",
    status: "computed",
    baseline_run_id: "run_actual",
    lineage: scenario.lineage,
    assumption_ids: ["asm_1"],
  },
  assumption_ids: ["asm_1"],
};
