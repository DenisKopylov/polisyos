import { expectNoA11yViolations } from "@/test/a11y";

import { Quantity } from "./Quantity";
import type { QuantityValue } from "./quantity.types";

const quantity: QuantityValue = {
  point: 0.23,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "effect_size",
  lineage: {
    id: "artifact:sha256:fixture",
    status: "verified",
    freshness: "current",
  },
  uncertainty: {
    ci_95: [0.15, 0.31],
    disputed: false,
    identifiability: "estimated",
  },
  quantity_class: "decision",
  label: "Effect size",
};

describe("Quantity accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <main>
        <Quantity value={quantity} precision={2} provenanceMode="off" />
      </main>,
    );
  });
});
