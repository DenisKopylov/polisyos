import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { CounterfactualModeSwitch } from "./CounterfactualModeSwitch";

describe("CounterfactualModeSwitch accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <CounterfactualModeSwitch value="actual" onChange={vi.fn()} />,
    );
  });
});
