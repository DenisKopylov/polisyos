import { describe, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { ScenarioPicker } from "./ScenarioPicker";
import { scenario } from "./counterfactualTestData";

describe("ScenarioPicker accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(
      <ScenarioPicker
        onChange={vi.fn()}
        scenarios={[scenario]}
        value={scenario.id}
      />,
    );
  });
});
