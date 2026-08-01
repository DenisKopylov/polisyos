import { describe, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { ScenarioManifestPanel } from "./ScenarioManifestPanel";
import { scenario } from "./counterfactualTestData";

describe("ScenarioManifestPanel accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    await expectNoA11yViolations(<ScenarioManifestPanel scenario={scenario} />);
  });
});
