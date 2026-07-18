import { expectNoA11yViolations } from "@/test/a11y";

import {
  MetricsSkeleton,
  PageSkeleton,
  PanelSkeleton,
} from "@polisyos/atlas-ui";

describe("Skeleton accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <div>
        <PageSkeleton />
        <PanelSkeleton rows={2} />
        <MetricsSkeleton count={2} />
      </div>,
    );
  });
});
