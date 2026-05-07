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
            id: "data",
            label: "Evidence registry",
            status: "ok",
            statusLabel: "Verified",
            timestamp: "2026-04-23 10:00",
            type: "data",
          },
          {
            id: "result",
            label: "Decision packet",
            status: "neutral",
            statusLabel: "Generated",
            type: "result",
          },
        ]}
      />,
      { initialEntries: ["/runs/run_123"] },
    );
  });
});
