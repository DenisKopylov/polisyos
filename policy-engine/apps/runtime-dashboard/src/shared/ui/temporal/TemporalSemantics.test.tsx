import { render, screen } from "@testing-library/react";

import { TimeSemanticsLabel } from "./TimeSemanticsLabel";

describe("TemporalSemantics", () => {
  it("renders missing epoch and as-of semantics as unknown or stale", () => {
    render(<TimeSemanticsLabel cacheAgeLabel="stale" freshness={null} />);

    expect(screen.getByTestId("time-semantics-valid-at")).toHaveTextContent(
      /Policy valid at:\s*unknown/u,
    );
    expect(screen.getByTestId("time-semantics-tx-at")).toHaveTextContent(
      /Knowledge tx at:\s*unknown/u,
    );
    expect(
      screen.getByTestId("time-semantics-payload-as-of"),
    ).toHaveTextContent(/Payload as of:\s*unknown/u);
    expect(screen.getByTestId("time-semantics-source-as-of")).toHaveTextContent(
      /Source as of:\s*unknown/u,
    );
    expect(screen.getByTestId("time-semantics-cache-age")).toHaveTextContent(
      /Cache age:\s*stale \(unrecognized\)/u,
    );
  });

  it("never treats observed_at as source_as_of", () => {
    render(
      <TimeSemanticsLabel
        freshness={{
          basis: "request_observation",
          observed_at: "2026-07-20T09:00:00Z",
          source_as_of: null,
          state: "observed",
        }}
      />,
    );

    expect(screen.getByTestId("time-semantics-source-as-of")).toHaveTextContent(
      /Source as of:\s*unknown/u,
    );
    expect(screen.getByTestId("time-semantics-observed-at")).toHaveTextContent(
      /Observed at:\s*2026-07-20T09:00:00Z/u,
    );
  });
});
