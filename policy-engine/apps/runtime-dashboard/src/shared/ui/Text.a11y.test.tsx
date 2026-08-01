import { expectNoA11yViolations } from "@/test/a11y";

import { Text } from "@polisyos/atlas-ui";

describe("Text accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <article>
        <Text as="h2">Evidence brief</Text>
        <Text className="mt-2">
          The dashboard renders prose with locale-aware typography helpers.
        </Text>
      </article>,
    );
  });
});
