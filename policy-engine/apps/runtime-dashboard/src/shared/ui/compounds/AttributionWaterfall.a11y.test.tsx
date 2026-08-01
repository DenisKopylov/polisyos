import { expectNoA11yViolations } from "@/test/a11y";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

import { AttributionWaterfall } from "./AttributionWaterfall";

describe("AttributionWaterfall accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <AttributionWaterfall
        baseValue={untracedDecisionQuantity({
          metricId: "test.attribution_baseline",
          point: 0.18,
        })}
        contributions={[
          { label: "Income support", value: 0.04, detail: "Positive lift" },
          { label: "Compliance burden", value: -0.02, detail: "Drag" },
        ]}
      />,
    );
  });
});
