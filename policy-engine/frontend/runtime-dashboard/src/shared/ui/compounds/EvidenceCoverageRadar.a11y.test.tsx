import { expectNoA11yViolations } from "@/test/a11y";

import { EvidenceCoverageRadar } from "./EvidenceCoverageRadar";

describe("EvidenceCoverageRadar accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <EvidenceCoverageRadar
        coverage={{
          academic: 0.8,
          dataset: 0.74,
          legal: 0.9,
          transport: 0.66,
        }}
      />,
    );
  });
});
