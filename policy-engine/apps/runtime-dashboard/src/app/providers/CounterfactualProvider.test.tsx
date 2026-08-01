import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { useMaybeCounterfactualInteraction } from "@/shared/ui/counterfactual/CounterfactualInteractionBridge";

import {
  CounterfactualProvider,
  useCounterfactual,
} from "./CounterfactualProvider";

function Probe() {
  const { mode, scenarioId, setMode, setScenarioId, resetScope } =
    useCounterfactual();
  return (
    <div>
      <output aria-label="scope">
        {mode}:{scenarioId ?? "none"}
      </output>
      <button
        type="button"
        onClick={() => {
          setScenarioId("scn_fixture");
          setMode("actual_vs_scenario");
        }}
      >
        set
      </button>
      <button type="button" onClick={() => resetScope()}>
        reset
      </button>
    </div>
  );
}

function SharedInteractionProbe() {
  const counterfactual = useMaybeCounterfactualInteraction();
  return (
    <output aria-label="shared interaction scope">
      {counterfactual?.mode}:{counterfactual?.scenarioId ?? "none"}
    </output>
  );
}

describe("CounterfactualProvider", () => {
  it("reads and writes scenario scope through the URL", async () => {
    window.history.replaceState(
      null,
      "",
      "/runs/run_1?scenario_id=scn_url&cf_mode=scenario_only",
    );

    render(
      <CounterfactualProvider>
        <Probe />
        <SharedInteractionProbe />
      </CounterfactualProvider>,
    );

    expect(screen.getByLabelText("scope")).toHaveTextContent(
      "scenario_only:scn_url",
    );
    expect(screen.getByLabelText("shared interaction scope")).toHaveTextContent(
      "scenario_only:scn_url",
    );

    await userEvent.click(screen.getByRole("button", { name: "set" }));
    expect(screen.getByLabelText("scope")).toHaveTextContent(
      "actual_vs_scenario:scn_fixture",
    );
    expect(screen.getByLabelText("shared interaction scope")).toHaveTextContent(
      "actual_vs_scenario:scn_fixture",
    );
    expect(window.location.search).toContain("scenario_id=scn_fixture");
    expect(window.location.search).toContain("cf_mode=actual_vs_scenario");

    await userEvent.click(screen.getByRole("button", { name: "reset" }));
    expect(screen.getByLabelText("scope")).toHaveTextContent("actual:none");
    expect(window.location.search).not.toContain("scenario_id=");
  });
});
