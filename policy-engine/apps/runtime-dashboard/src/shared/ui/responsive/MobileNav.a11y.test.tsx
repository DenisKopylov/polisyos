import { FileText, Home } from "lucide-react";

import { expectNoA11yViolations } from "@/test/a11y";

import { MobileNav } from "./MobileNav";

describe("MobileNav accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <MobileNav
        ariaLabel="Primary navigation"
        atlasEnabled
        items={[
          { Icon: Home, active: false, label: "Home", path: "/" },
          { Icon: FileText, active: true, label: "Runs", path: "/runs" },
        ]}
        renderItem={(item, className, children) => (
          <a
            href={item.path}
            className={className}
            aria-current={item.active ? "page" : undefined}
          >
            {children}
          </a>
        )}
      />,
      {
        initialEntries: ["/runs"],
        interactiveProviders: true,
      },
    );
  });
});
