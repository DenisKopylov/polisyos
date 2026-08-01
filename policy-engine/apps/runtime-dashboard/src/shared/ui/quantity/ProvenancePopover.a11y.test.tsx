import { screen } from "@testing-library/react";

import { expectNoA11yViolations } from "@/test/a11y";

import { ProvenancePopover } from "./ProvenancePopover";
import type { QuantityValue } from "./quantity.types";

const quantity: QuantityValue = {
  point: 0.23,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "effect_size",
  lineage: {
    id: "untraced",
    status: "untraced",
    freshness: "unknown",
    reason_code: "fixture_without_lineage",
    tracking_issue: "POLICYOS-QUANTITY-0",
  },
  quantity_class: "decision",
  label: "Effect size",
};

describe("ProvenancePopover accessibility", () => {
  it("has no detectable accessibility violations when open", async () => {
    await expectNoA11yViolations(
      <main>
        <ProvenancePopover
          quantity={quantity}
          open
          onOpenChange={() => undefined}
        >
          <button type="button">Open provenance</button>
        </ProvenancePopover>
      </main>,
      { includeDocumentBody: true },
    );

    expect(
      screen.getByRole("dialog", { name: "Provenance" }),
    ).toBeVisible();
  });
});
