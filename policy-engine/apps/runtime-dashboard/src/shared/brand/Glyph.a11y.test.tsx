import { expectNoA11yViolations } from "@/test/a11y";

import { Glyph } from "./Glyph";

describe("Glyph accessibility", () => {
  it("has no detectable accessibility violations without local authority clothing", async () => {
    const view = await expectNoA11yViolations(
      <div>
        <Glyph name="evidence" size={14} title="Evidence provenance" />
      </div>,
    );

    expect(
      view.container.querySelector("[data-glyph-intent]") === null,
    ).toBe(true);
  });
});
