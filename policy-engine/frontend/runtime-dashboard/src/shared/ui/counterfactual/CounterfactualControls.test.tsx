import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CounterfactualProvider } from "@/app/providers/CounterfactualProvider";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import type {
  CounterfactualMetric,
  QuantityValue,
} from "@/shared/ui/quantity/quantity.types";

import { CounterfactualMetricChart } from "./CounterfactualMetricChart";
import { CounterfactualModeSwitch } from "./CounterfactualModeSwitch";
import { ScenarioManifestPanel } from "./ScenarioManifestPanel";
import { ScenarioPicker } from "./ScenarioPicker";
import type { ScenarioListPayload } from "@/api/validators";

const scenario = {
  id: "scn_fixture",
  baseline_run_id: "run_actual",
  status: "computed",
  policy_question: "What if policy cost is capped?",
  author: "operator",
  model_family: "runtime-counterfactual-linearized",
  model_lineage: {
    id: "scenario:scn_fixture:model",
    status: "pending",
    freshness: "current",
    summary: { source: "scenario" },
  },
  interventions: [],
  assumptions: [
    {
      id: "asm_1",
      label: "No external shock",
      status: "operator_assumption",
      lineage: {
        id: "scenario:scn_fixture:assumption",
        status: "pending",
        freshness: "current",
        summary: { source: "operator" },
      },
    },
  ],
} satisfies NonNullable<ScenarioListPayload["scenarios"]>[number];

function Providers({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <CounterfactualProvider>{children}</CounterfactualProvider>
    </LocaleProvider>
  );
}

describe("counterfactual controls", () => {
  it("changes mode with accessible radio buttons", async () => {
    render(<CounterfactualModeSwitch />, { wrapper: Providers });

    await userEvent.click(
      screen.getByRole("radio", { name: "Actual + Scenario" }),
    );

    expect(
      screen.getByRole("radio", { name: "Actual + Scenario" }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("chooses a named scenario and shows manifest assumptions", async () => {
    const onChange = vi.fn();
    render(
      <>
        <ScenarioPicker scenarios={[scenario]} onChange={onChange} />
        <ScenarioManifestPanel scenario={scenario} />
      </>,
      { wrapper: Providers },
    );

    await userEvent.selectOptions(screen.getByLabelText("Scenario"), [
      "scn_fixture",
    ]);

    expect(onChange).toHaveBeenCalledWith("scn_fixture");
    expect(screen.getByText("No external shock")).toBeInTheDocument();
    expect(screen.getAllByText("Computed").length).toBeGreaterThan(0);
  });

  it("renders actual, scenario and delta chart with assumption badges", () => {
    render(
      <CounterfactualMetricChart
        metric={counterfactualMetric}
        assumptions={scenario.assumptions}
      />,
      { wrapper: Providers },
    );

    expect(screen.getByTestId("counterfactual-metric-chart")).toHaveAttribute(
      "aria-label",
      "Employment: baseline, scenario and difference chart for scn_fixture",
    );
    expect(screen.getByText("Actual")).toBeInTheDocument();
    expect(screen.getByText("Scenario")).toBeInTheDocument();
    expect(screen.getByText("Delta")).toBeInTheDocument();
    expect(screen.getByText("No external shock")).toBeInTheDocument();
    expect(screen.getAllByText(/95% CI/)).toHaveLength(3);
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
  uncertainty: {
    ci_95: [0.16, 0.24],
    method: "bootstrap",
    identifiability: "estimated",
    disputed: false,
  },
  time: { valid_at: "2026-04-15T12:00:00Z" },
  quantity_class: "decision",
};

const scenarioQuantity: QuantityValue = {
  ...actual,
  point: 0.24,
  lineage: {
    id: "scenario:scn_fixture:projection",
    status: "pending",
    freshness: "current",
    summary: { source: "scenario", assumptions: "asm_1" },
  },
  uncertainty: {
    ci_95: [0.19, 0.29],
    method: "simulation",
    identifiability: "assumed",
    disputed: false,
  },
  time: { ...actual.time, scenario_id: "scn_fixture" },
};

const counterfactualMetric: CounterfactualMetric = {
  metric_id: "employment_rate_delta",
  label: "Employment",
  actual,
  counterfactual: scenarioQuantity,
  delta: {
    ...scenarioQuantity,
    point: 0.04,
    metric_id: "employment_rate_delta.counterfactual_delta",
    label: "Employment delta",
    uncertainty: {
      ci_95: [-0.01, 0.09],
      method: "simulation",
      identifiability: "assumed",
      disputed: false,
    },
  },
  scenario_ref: {
    id: "scn_fixture",
    status: "computed",
    baseline_run_id: "run_actual",
    lineage: scenarioQuantity.lineage,
    assumption_ids: ["asm_1"],
  },
  assumption_ids: ["asm_1"],
};
