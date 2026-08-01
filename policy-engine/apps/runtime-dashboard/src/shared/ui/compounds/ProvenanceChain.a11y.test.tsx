import { expectNoA11yViolations } from "@/test/a11y";

import { ProvenanceChain } from "./ProvenanceChain";

describe("ProvenanceChain accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <ProvenanceChain
        steps={[
          {
            detail: "Registry snapshot was loaded.",
            href: "/evidence",
            lineage: {
              id: "data",
              kind: "dataset",
              label: "Evidence registry",
            },
            source: "recorded-lineage",
            timestamp: "2026-04-23 10:00",
          },
          {
            lineage: {
              id: "result",
              kind: "result",
              label: "Decision packet",
            },
            source: "recorded-lineage",
          },
        ]}
      />,
      { initialEntries: ["/runs/run_123"] },
    );
  });
});
