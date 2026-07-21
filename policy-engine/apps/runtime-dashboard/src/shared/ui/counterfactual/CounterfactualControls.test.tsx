import { type ReactNode, useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { CounterfactualMetricChart } from "./CounterfactualMetricChart";
import {
  CounterfactualInteractionBridgeProvider,
  type CounterfactualMode,
} from "./CounterfactualInteractionBridge";
import { CounterfactualModeSwitch } from "./CounterfactualModeSwitch";
import { ScenarioManifestPanel } from "./ScenarioManifestPanel";
import { ScenarioPicker } from "./ScenarioPicker";
import { counterfactualMetric, scenario } from "./counterfactualTestData";

function Providers({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<CounterfactualMode>("actual");
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  return (
    <LocaleProvider>
      <CounterfactualInteractionBridgeProvider
        value={{ mode, scenarioId, setMode, setScenarioId }}
      >
        {children}
      </CounterfactualInteractionBridgeProvider>
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

  it("shows only assumptions bound by the generated metric artifact", () => {
    render(
      <CounterfactualMetricChart
        metric={counterfactualMetric}
        assumptions={[
          ...scenario.assumptions,
          {
            ...scenario.assumptions[0],
            id: "asm_unbound",
            label: "Unbound local assumption",
          },
        ]}
      />,
      { wrapper: Providers },
    );

    expect(screen.getByText("No external shock")).toBeInTheDocument();
    expect(
      screen.queryByText("Unbound local assumption"),
    ).not.toBeInTheDocument();
  });

  it("keeps an absent metric point unknown instead of drawing a zero value", () => {
    render(
      <CounterfactualMetricChart
        metric={{
          ...counterfactualMetric,
          actual: { ...counterfactualMetric.actual, point: null },
        }}
      />,
      { wrapper: Providers },
    );

    expect(screen.getByTestId("counterfactual-bar-actual")).toHaveAttribute(
      "data-counterfactual-value-state",
      "unknown",
    );
    expect(screen.getByTestId("counterfactual-bar-actual")).not.toHaveAttribute(
      "style",
    );
    expect(
      within(screen.getByTestId("counterfactual-value-actual")).getByTestId(
        "quantity",
      ),
    ).toHaveAttribute("data-quantity-presentation", "unknown");
    expect(
      screen.getByTestId("counterfactual-value-actual"),
    ).not.toHaveTextContent("0");
  });

  it("gives every scenario picker its own label target", () => {
    render(
      <>
        <ScenarioPicker scenarios={[scenario]} value="scn_fixture" />
        <ScenarioPicker scenarios={[scenario]} value="scn_fixture" />
      </>,
      { wrapper: Providers },
    );

    const pickerIds = screen
      .getAllByRole("combobox", { name: "Scenario" })
      .map((picker) => picker.id);
    expect(new Set(pickerIds).size).toBe(2);
  });
});
