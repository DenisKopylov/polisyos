import { vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { PullToRefresh } from "./PullToRefresh";

describe("PullToRefresh accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <PullToRefresh onRefresh={vi.fn(async () => undefined)}>
        <article>Refreshable decision feed</article>
      </PullToRefresh>,
    );
  });
});
