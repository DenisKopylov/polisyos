import { Search } from "lucide-react";

import { expectNoA11yViolations } from "@/test/a11y";

import { Icon, Spinner } from "./Icon";

describe("Icon accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div className="flex items-center gap-3">
        <Icon icon={Search} label="Search" />
        <Spinner />
      </div>,
    );
  });
});
