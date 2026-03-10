import { expectNoA11yViolations } from "@/test/a11y";

import { Card } from "./Card";

describe("Card accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <Card>
        <h2>Decision queue</h2>
        <p>Awaiting operator review.</p>
      </Card>,
    );
  });
});
