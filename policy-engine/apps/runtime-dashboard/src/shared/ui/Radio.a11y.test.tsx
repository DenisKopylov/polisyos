import { expectNoA11yViolations } from "@/test/a11y";

import { Radio } from "@polisyos/atlas-ui";

describe("Radio accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Data source binding</legend>
        <div className="flex items-center gap-3 text-sm">
          <Radio
            id="radio-data-source-snapshot"
            name="data-source"
            value="snapshot"
            aria-labelledby="radio-data-source-snapshot-label"
            defaultChecked
          />
          <span id="radio-data-source-snapshot-label">Snapshot</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Radio
            id="radio-data-source-bindings"
            name="data-source"
            value="bindings"
            aria-labelledby="radio-data-source-bindings-label"
          />
          <span id="radio-data-source-bindings-label">Bindings</span>
        </div>
      </fieldset>,
    );
  });
});
