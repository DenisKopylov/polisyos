import { expectNoA11yViolations } from "@/test/a11y";

import { ScrollArea } from "./ScrollArea";

describe("ScrollArea accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <ScrollArea
        aria-label="Audit timeline entries"
        className="h-28 w-64 rounded-xl border"
      >
        <div className="space-y-2 p-3">
          <p>Policy draft validated.</p>
          <p>Evidence bundle refreshed.</p>
          <p>Decision packet exported.</p>
          <p>Stakeholder deck published.</p>
        </div>
      </ScrollArea>,
    );
  });
});
