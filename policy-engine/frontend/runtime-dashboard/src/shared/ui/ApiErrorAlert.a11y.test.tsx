import { expectNoA11yViolations } from "@/test/a11y";

import { ApiErrorAlert } from "./ApiErrorAlert";

describe("ApiErrorAlert accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <ApiErrorAlert error={new Error("Runtime unavailable")} />,
    );
  });
});
