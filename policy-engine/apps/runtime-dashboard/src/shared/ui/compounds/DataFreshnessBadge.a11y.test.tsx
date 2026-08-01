import { expectNoA11yViolations } from "@/test/a11y";
import { screen } from "@testing-library/react";

import { DataFreshnessBadge } from "./DataFreshnessBadge";

describe("DataFreshnessBadge accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <DataFreshnessBadge
        freshness={{
          basis: "source_timestamp",
          observed_at: "2026-04-23T10:05:00.000Z",
          source_as_of: "2026-04-23T10:00:00.000Z",
          state: "observed",
        }}
      />,
    );

    expect(
      screen.getByText(
        "Source as of: 2026-04-23T10:00:00.000Z; observed at: 2026-04-23T10:05:00.000Z",
      ),
    ).toBeInTheDocument();
  });
});
