import type { PropsWithChildren } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  TemporalCursorProvider,
  useTemporalCursor,
} from "./TemporalCursorProvider";

function wrapper({ children }: PropsWithChildren) {
  return <TemporalCursorProvider>{children}</TemporalCursorProvider>;
}

describe("TemporalCursorProvider", () => {
  it("initializes from URL shorthand", () => {
    window.history.replaceState({}, "", "/runs/run-1?t=2026-04-15T12:00:00Z");

    const { result } = renderHook(() => useTemporalCursor(), { wrapper });

    expect(result.current.committedScope?.validAt).toBe(
      "2026-04-15T12:00:00.000Z",
    );
  });

  it("commits canonical URL params", () => {
    window.history.replaceState({}, "", "/runs/run-1");
    const { result } = renderHook(() => useTemporalCursor(), { wrapper });

    act(() => {
      result.current.commitScope({
        branch: "main",
        txAt: "2026-04-16T09:20:00Z",
        validAt: "2026-04-15T12:00:00Z",
      });
    });

    expect(window.location.search).toContain(
      "valid_at=2026-04-15T12%3A00%3A00.000Z",
    );
    expect(window.location.search).toContain(
      "tx_at=2026-04-16T09%3A20%3A00.000Z",
    );
    expect(window.location.search).toContain("branch=main");
  });

  it("steps and clamps valid time to the known range", () => {
    window.history.replaceState({}, "", "/runs/run-1");
    const { result } = renderHook(() => useTemporalCursor(), { wrapper });

    act(() => {
      result.current.setTemporalCapabilities({
        defaultScope: {
          txAt: "2026-04-20T00:00:00Z",
          validAt: "2026-04-15T00:00:00Z",
        },
        eventPoints: [],
        resolution: "event",
        runId: "run-1",
        surfaces: [],
        txRange: {
          earliest: "2026-04-10T00:00:00Z",
          latest: "2026-04-20T00:00:00Z",
        },
        validRange: {
          earliest: "2026-04-10T00:00:00Z",
          latest: "2026-04-20T00:00:00Z",
        },
      });
    });

    act(() => {
      result.current.commitScope({
        validAt: "2026-04-19T00:00:00Z",
      });
      result.current.stepValidTime(10 * 24 * 60 * 60 * 1000);
    });

    expect(result.current.committedScope?.validAt).toBe(
      "2026-04-20T00:00:00.000Z",
    );
  });
});
