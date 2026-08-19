import { render, screen } from "@testing-library/react";

import { observeCachePosture } from "@/api/cacheDiscipline";

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

  it.each([
    {
      fetchStatus: "idle",
      isFetchedAfterMount: true,
      isStale: false,
      posture: "live",
    },
    {
      fetchStatus: "idle",
      isFetchedAfterMount: false,
      isStale: false,
      posture: "cached",
    },
    {
      fetchStatus: "fetching",
      isFetchedAfterMount: true,
      isStale: true,
      posture: "stale",
    },
  ])("renders the issued $posture posture with owner as_of", (lifecycle) => {
    const cacheObservation = observeCachePosture(
      { data: {}, ...lifecycle },
      "2026-08-19T09:30:00Z",
    );

    render(<TimeSemanticsLabel cacheObservation={cacheObservation} />);

    expect(
      screen.getByTestId("time-semantics-cache-posture"),
    ).toHaveTextContent(
      new RegExp(`Cache posture:\\s*${lifecycle.posture}`, "u"),
    );
    expect(
      screen.getByTestId("time-semantics-cache-owner-as-of"),
    ).toHaveTextContent("2026-08-19T09:30:00Z");
  });

  it.each([
    { asOf: "2026-08-19T09:30:00Z", posture: "offline_queued" },
    { asOf: null, posture: "cached" },
    { asOf: "not-owner-time", posture: "live" },
  ])("fails a malformed or novel cache observation closed", (observation) => {
    render(<TimeSemanticsLabel cacheObservation={observation as never} />);

    expect(
      screen.getByTestId("time-semantics-cache-posture"),
    ).toHaveTextContent(/Cache posture:\s*unrecognized/u);
    expect(
      screen.getByTestId("time-semantics-cache-owner-as-of"),
    ).toHaveTextContent(/Cache owner as of:\s*unknown/u);
    expect(screen.queryByText(/offline_queued/u)).not.toBeInTheDocument();
  });

  it("rejects a frozen structural lookalike that the cache owner did not issue", () => {
    const forgedObservation = Object.freeze({
      asOf: "2026-08-19T09:30:00Z",
      posture: "live",
    });

    render(
      <TimeSemanticsLabel cacheObservation={forgedObservation as never} />,
    );

    expect(
      screen.getByTestId("time-semantics-cache-posture"),
    ).toHaveTextContent(/Cache posture:\s*unrecognized/u);
    expect(
      screen.getByTestId("time-semantics-cache-owner-as-of"),
    ).toHaveTextContent(/Cache owner as of:\s*unknown/u);
  });

  it("contains hostile observation getters without re-reading them", () => {
    let postureReads = 0;
    const hostile = Object.defineProperty(
      { asOf: "2026-08-19T09:30:00Z" },
      "posture",
      {
        enumerable: true,
        get() {
          postureReads += 1;
          throw new Error("hostile posture getter");
        },
      },
    );

    expect(() =>
      render(<TimeSemanticsLabel cacheObservation={hostile as never} />),
    ).not.toThrow();
    expect(postureReads).toBeLessThanOrEqual(1);
    expect(
      screen.getByTestId("time-semantics-cache-posture"),
    ).toHaveTextContent(/unrecognized/u);
  });
});
