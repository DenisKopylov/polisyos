import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import { expectNoA11yViolations } from "@/test/a11y";

import { ProvenanceStrip } from "./ProvenanceStrip";

const items: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
    trustMetadata: {
      dispute_status: "none",
      freshness: "current",
      verification_status: "verified",
    },
  },
  { id: "evidence", glyph: "evidence", label: "Strong evidence" },
];

describe("ProvenanceStrip accessibility", () => {
  it("ProvenanceStrip emits no default intent attribute", async () => {
    const view = await expectNoA11yViolations(
      <ProvenanceStrip items={items} title="Provenance" />,
    );

    expect(view.container.querySelector("[data-intent]")).toBeNull();
    expect(view.container.querySelector("[data-glyph-intent]")).toBeNull();
    expect(
      view.container.querySelectorAll("[data-verification-presentation]"),
    ).toHaveLength(1);
  });
});
