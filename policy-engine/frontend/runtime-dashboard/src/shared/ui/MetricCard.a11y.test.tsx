import { expectNoA11yViolations } from "@/test/a11y";

import { MetricCard } from "./MetricCard";

describe("MetricCard accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <MetricCard label="Blocked runs" value="3" meta="Needs operator review" />,
    );
  });
});
