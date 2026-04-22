import type { ProvenanceItem } from "@/shared/brand/provenance-adapter";
import { expectNoA11yViolations } from "@/test/a11y";

import { ProvenanceStrip } from "./ProvenanceStrip";

const items: ProvenanceItem[] = [
  { id: "freshness", glyph: "freshness", label: "Fresh", intent: "verified" },
  {
    id: "governance",
    glyph: "governance-pass",
    label: "Governance pass",
    intent: "verified",
  },
  { id: "evidence", glyph: "evidence", label: "Strong evidence" },
];

describe("ProvenanceStrip accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <ProvenanceStrip items={items} title="Provenance" />,
    );
  });
});
