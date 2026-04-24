import { expectNoA11yViolations } from "@/test/a11y";

import { Glyph } from "./Glyph";

describe("Glyph accessibility", () => {
  it("has no detectable accessibility violations across semantic variants", async () => {
    await expectNoA11yViolations(
      <div className="flex items-center gap-4">
        <Glyph name="intervention" size={12} />
        <Glyph name="evidence" intent="verified" size={14} />
        <Glyph name="counterfactual" size={16} strokeStyle="dashed" />
        <Glyph name="identifiability" diacritic="strict" size={24} />
      </div>,
    );
  });
});
