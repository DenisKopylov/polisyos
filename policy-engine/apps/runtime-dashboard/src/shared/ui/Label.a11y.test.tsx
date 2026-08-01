import { expectNoA11yViolations } from "@/test/a11y";

import { Input, Label } from "@polisyos/atlas-ui";

describe("Label accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="space-y-2">
        <Label htmlFor="policy-name">Policy name</Label>
        <Input id="policy-name" defaultValue="Food price response" />
      </div>,
    );
  });
});
