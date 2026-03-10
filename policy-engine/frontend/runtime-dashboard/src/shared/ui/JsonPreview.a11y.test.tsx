import { expectNoA11yViolations } from "@/test/a11y";

import JsonPreview from "./JsonPreview";

describe("JsonPreview accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <JsonPreview
        data={{
          blockers: 1,
          decision: "approve_with_conditions",
        }}
      />,
    );
  });
});
