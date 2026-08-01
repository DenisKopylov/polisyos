import { expectNoA11yViolations } from "@/test/a11y";

import { GovernancePassGrid } from "./GovernancePassGrid";

describe("GovernancePassGrid accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <GovernancePassGrid
        passes={[
          {
            detail: "All required source references are present.",
            durationMs: 120,
            id: "provenance",
            label: "Provenance law",
            status: "pass",
            vocabulary: "owner_diagnostic",
          },
          {
            detail: "Operator review is still required.",
            id: "review",
            label: "Human review",
            status: "warning",
            vocabulary: "owner_diagnostic",
          },
        ]}
      />,
    );
  });
});
