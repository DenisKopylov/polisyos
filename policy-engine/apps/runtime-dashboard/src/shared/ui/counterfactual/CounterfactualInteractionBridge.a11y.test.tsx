import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { CounterfactualInteractionBridgeProvider } from "./CounterfactualInteractionBridge";

describe("CounterfactualInteractionBridgeProvider accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <CounterfactualInteractionBridgeProvider
        value={{
          mode: "actual",
          scenarioId: null,
          setMode: vi.fn(),
          setScenarioId: vi.fn(),
        }}
      >
        <span>Counterfactual controls</span>
      </CounterfactualInteractionBridgeProvider>,
    );
  });
});
