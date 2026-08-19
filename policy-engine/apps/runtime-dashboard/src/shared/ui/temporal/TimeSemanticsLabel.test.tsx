import { render, screen } from "@testing-library/react";

import { TimeSemanticsLabel } from "./TimeSemanticsLabel";

describe("TimeSemanticsLabel", () => {
  it("never maps source observation state to cache-age staleness", () => {
    render(
      <TimeSemanticsLabel
        freshness={{
          basis: "source_timestamp",
          observed_at: "2026-07-20T09:00:00Z",
          source_as_of: "2026-07-19T12:00:00Z",
          state: "observed",
        }}
      />,
    );

    expect(screen.getByTestId("time-semantics-source-state")).toHaveTextContent(
      /Source state:\s*observed/u,
    );
    expect(screen.getByTestId("time-semantics-cache-age")).toHaveTextContent(
      /Cache age:\s*unknown \(unrecognized\)/u,
    );
    expect(
      screen.getByTestId("time-semantics-cache-age"),
    ).not.toHaveTextContent(/stale/iu);
  });

  it("renders caller-owned temporal entries inside the semantic list", () => {
    render(
      <TimeSemanticsLabel>
        <div data-testid="owned-temporal-entry">
          <dt>Owner posture:</dt>
          <dd>owner projection</dd>
        </div>
      </TimeSemanticsLabel>,
    );

    expect(screen.getByTestId("owned-temporal-entry")).toHaveTextContent(
      "owner projection",
    );
  });
});
