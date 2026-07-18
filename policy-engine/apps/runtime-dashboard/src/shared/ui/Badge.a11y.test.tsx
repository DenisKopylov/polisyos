import { expectNoA11yViolations } from "@/test/a11y";

import { Badge } from "@polisyos/atlas-ui";

describe("Badge accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(<Badge kind="ok">Healthy</Badge>);
  });
});
