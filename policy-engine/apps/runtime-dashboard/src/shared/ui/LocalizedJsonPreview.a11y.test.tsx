import { expectNoA11yViolations } from "@/test/a11y";

import { LocalizedJsonPreview } from "./LocalizedJsonPreview";

describe("LocalizedJsonPreview accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <LocalizedJsonPreview
        data={{
          availability: "artifact_missing",
          fixture_authority: "fixture_only",
          reason: "No producer-signed artifact is available for this preview.",
        }}
      />,
    );
  });
});
