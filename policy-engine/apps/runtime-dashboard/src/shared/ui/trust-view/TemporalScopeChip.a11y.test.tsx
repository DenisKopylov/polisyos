import { expectNoA11yViolations } from "@/test/a11y";

import { TemporalScopeChip } from "./TemporalScopeChip";

describe("TemporalScopeChip accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <TemporalScopeChip
        scope={{
          tx_at: "2026-07-20T10:00:00Z",
          valid_at: "2026-07-20T09:00:00Z",
        }}
      />,
    );
  });
});
