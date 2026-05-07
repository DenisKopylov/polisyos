import { expectNoA11yViolations } from "@/test/a11y";

import { DetailLayout } from "./DetailLayout";

describe("DetailLayout accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <DetailLayout
        header={<h2>Decision detail</h2>}
        sidebar={<nav aria-label="Decision sections">Summary</nav>}
        content={<article>Decision content</article>}
        footer={<button type="button">Close</button>}
      />,
    );
  });
});
