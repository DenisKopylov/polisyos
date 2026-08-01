import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import { TimeSemanticsLabel } from "./TimeSemanticsLabel";

describe("TimeSemanticsLabel accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    const { container } = render(
      <TimeSemanticsLabel
        cacheAgeLabel="owner-extension"
        freshness={{
          basis: "source_timestamp",
          observed_at: "2026-04-20T12:05:00Z",
          source_as_of: "2026-04-20T12:00:00Z",
          state: "observed",
        }}
        payloadAsOf="2026-04-20T12:06:00Z"
        txAt="2026-04-20T12:04:00Z"
        validAt="2026-04-20T12:00:00Z"
      />,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
