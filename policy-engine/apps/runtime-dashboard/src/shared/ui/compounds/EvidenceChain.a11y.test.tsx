import { expectNoA11yViolations } from "@/test/a11y";

import { EvidenceChain } from "./EvidenceChain";

describe("EvidenceChain accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <EvidenceChain
        title="Evidence chain"
        emptyTitle="No evidence"
        emptyBody="Attach evidence to continue."
        items={[
          {
            artifactId: "artifact_123",
            href: "/artifacts/artifact_123",
            label: "Administrative registry",
            meta: "Fresh at 2026-04-23",
          },
        ]}
      />,
      { initialEntries: ["/runs/run_123"] },
    );
  });
});
