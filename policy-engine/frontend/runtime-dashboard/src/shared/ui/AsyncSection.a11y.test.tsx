import { expectNoA11yViolations } from "@/test/a11y";

import { AsyncSection } from "./AsyncSection";

describe("AsyncSection accessibility", () => {
  it("has no detectable accessibility violations in the resolved state", async () => {
    await expectNoA11yViolations(
      <AsyncSection query={{ isError: false, isLoading: false }}>
        <section aria-label="Loaded content">Loaded</section>
      </AsyncSection>,
    );
  });
});
