import { vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { SwipeableDrawer } from "./SwipeableDrawer";

describe("SwipeableDrawer accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <SwipeableDrawer open onClose={vi.fn()} title="Navigation">
        <nav aria-label="Drawer navigation">
          <a href="/runs">Runs</a>
        </nav>
      </SwipeableDrawer>,
      { includeDocumentBody: true, initialEntries: ["/runs"] },
    );
  });
});
