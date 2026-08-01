import { expectNoA11yViolations } from "@/test/a11y";

import { StatusTimeline } from "./StatusTimeline";

describe("StatusTimeline accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <StatusTimeline
        emptyTitle="No events"
        emptyBody="Timeline events will appear here."
        items={[
          {
            body: "Decision packet generated successfully.",
            id: "generated",
            timestamp: "2026-04-23 10:00",
            title: "Generated",
            recordedState: "completed",
          },
        ]}
      />,
    );
  });
});
