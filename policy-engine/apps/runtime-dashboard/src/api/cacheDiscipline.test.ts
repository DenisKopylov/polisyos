import { describe, expect, it, vi } from "vitest";

import {
  type CacheObservation,
  isIssuedCacheObservation,
  observeCachePosture,
  presentCacheObservation,
} from "./cacheDiscipline";

describe("cache discipline", () => {
  it("rejects raw structural cache observations at compile time", () => {
    // @ts-expect-error Cache posture can only be issued from the observer lifecycle.
    const structuralLookalike: CacheObservation = {
      asOf: "2026-08-09T10:00:00Z",
      posture: "live",
    };

    expect(structuralLookalike.posture).toBe("live");
    expect(isIssuedCacheObservation(structuralLookalike)).toBe(false);
  });

  it("recognizes only cache observations issued by the lifecycle owner", () => {
    const issued = observeCachePosture(
      {
        data: {},
        fetchStatus: "idle",
        isFetchedAfterMount: true,
        isStale: false,
      },
      "2026-08-09T10:00:00Z",
    );

    expect(isIssuedCacheObservation(issued)).toBe(true);
    expect(isIssuedCacheObservation(Object.freeze({ ...issued }))).toBe(false);
    expect(isIssuedCacheObservation(new Proxy(issued, {}))).toBe(false);
  });

  it("projects only owner-issued observations into presentation data", () => {
    const issued = observeCachePosture(
      {
        data: {},
        fetchStatus: "idle",
        isFetchedAfterMount: true,
        isStale: false,
      },
      "2026-08-09T10:00:00Z",
    );
    const structuralLookalike = Object.freeze({
      asOf: "2026-08-09T10:00:00Z",
      posture: "live",
    });
    let postureReads = 0;
    const hostile = Object.defineProperty(
      { asOf: "2026-08-09T10:00:00Z" },
      "posture",
      {
        enumerable: true,
        get() {
          postureReads += 1;
          throw new Error("hostile posture getter");
        },
      },
    );

    expect(presentCacheObservation(issued)).toEqual({
      ownerAsOf: "2026-08-09T10:00:00Z",
      posture: "live",
    });
    expect(presentCacheObservation(structuralLookalike)).toEqual({
      ownerAsOf: null,
      posture: "unrecognized",
    });
    expect(presentCacheObservation(hostile)).toEqual({
      ownerAsOf: null,
      posture: "unrecognized",
    });
    expect(postureReads).toBe(0);
  });

  it("returns unrecognized for a novel observer lifecycle or absent owner as_of", () => {
    expect(
      observeCachePosture(
        {
          data: { source_as_of: "2026-08-09T09:00:00Z" },
          fetchStatus: "deferred",
          isFetchedAfterMount: true,
          isStale: false,
        },
        "2026-08-09T10:00:00Z",
      ),
    ).toEqual({ asOf: null, posture: "unrecognized" });

    expect(
      observeCachePosture(
        {
          data: { source_as_of: "2026-08-09T09:00:00Z" },
          fetchStatus: "idle",
          isFetchedAfterMount: false,
          isStale: false,
        },
        undefined,
      ),
    ).toEqual({ asOf: null, posture: "unrecognized" });

    expect(
      observeCachePosture(
        {
          data: { source_as_of: "2026-08-09T09:00:00Z" },
          fetchStatus: "idle",
          isFetchedAfterMount: false,
          isStale: false,
        },
        "not-an-owner-time",
      ),
    ).toEqual({ asOf: null, posture: "unrecognized" });

    expect(
      observeCachePosture(
        {
          data: { source_as_of: "2026-08-09T09:00:00Z" },
          fetchStatus: "idle",
          isFetchedAfterMount: false,
          isStale: false,
        },
        "2026-02-30T10:00:00Z",
      ),
    ).toEqual({ asOf: null, posture: "unrecognized" });
  });

  it("refuses an observation without query data", () => {
    for (const data of [undefined, null]) {
      expect(
        observeCachePosture(
          {
            data,
            fetchStatus: "idle",
            isFetchedAfterMount: true,
            isStale: false,
          },
          "2026-08-09T10:00:00Z",
        ),
      ).toEqual({ asOf: null, posture: "unrecognized" });
    }
  });

  it("accepts canonical UTC and offset owner timestamps", () => {
    for (const asOf of ["2026-08-09T10:00:00Z", "2026-08-09T12:00:00+02:00"]) {
      expect(
        observeCachePosture(
          {
            data: { source_as_of: "2026-08-09T09:00:00Z" },
            fetchStatus: "idle",
            isFetchedAfterMount: false,
            isStale: false,
          },
          asOf,
        ),
      ).toEqual({ asOf, posture: "cached" });
    }
  });

  it("derives identical postures despite source timestamp and wall-clock changes", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2030-01-01T00:00:00Z"));
    const oldOwnerPacket = observeCachePosture(
      {
        data: {
          freshness: {
            observed_at: "2020-01-01T00:00:00Z",
            source_as_of: "2020-01-01T00:00:00Z",
          },
        },
        fetchStatus: "idle",
        isFetchedAfterMount: false,
        isStale: false,
      },
      "2020-01-01T00:00:00Z",
    );

    vi.setSystemTime(new Date("2040-01-01T00:00:00Z"));
    const newOwnerPacket = observeCachePosture(
      {
        data: {
          freshness: {
            observed_at: "2039-12-31T23:59:59Z",
            source_as_of: "2039-12-31T23:59:59Z",
          },
        },
        fetchStatus: "idle",
        isFetchedAfterMount: false,
        isStale: false,
      },
      "2039-12-31T23:59:59Z",
    );
    vi.useRealTimers();

    expect(oldOwnerPacket.posture).toBe("cached");
    expect(newOwnerPacket.posture).toBe("cached");
  });

  it("marks retained stale data from the observer lifecycle", () => {
    expect(
      observeCachePosture(
        {
          data: { freshness: { observed_at: "2026-08-09T09:00:00Z" } },
          fetchStatus: "fetching",
          isFetchedAfterMount: false,
          isStale: true,
        },
        "2026-08-09T10:00:00Z",
      ),
    ).toEqual({ asOf: "2026-08-09T10:00:00Z", posture: "stale" });
  });

  it("recognizes a current owner packet as live", () => {
    expect(
      observeCachePosture(
        {
          data: { source_as_of: "2026-08-09T09:00:00Z" },
          fetchStatus: "idle",
          isFetchedAfterMount: true,
          isStale: false,
        },
        "2026-08-09T10:00:00Z",
      ),
    ).toEqual({ asOf: "2026-08-09T10:00:00Z", posture: "live" });
  });
});
