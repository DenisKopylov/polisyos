import { expectNoA11yViolations } from "@/test/a11y";
import { screen } from "@testing-library/react";

import { MethodologyBadge } from "./MethodologyBadge";

describe("MethodologyBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(<MethodologyBadge methodology="did" />);

    expect(screen.getByRole("button", { name: /DiD/i })).toBeInTheDocument();
  });
});
