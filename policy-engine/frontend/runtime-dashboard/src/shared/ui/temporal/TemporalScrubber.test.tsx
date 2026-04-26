import type { PropsWithChildren } from "react";
import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  TemporalCursorProvider,
  useTemporalCursor,
} from "@/app/providers/TemporalCursorProvider";
import { createTestQueryClient } from "@/test/queryClient";
import { ReducedMotionProvider } from "@/shared/a11y";
import { TemporalScrubber } from "./TemporalScrubber";

function TemporalHarness() {
  const { setTemporalCapabilities } = useTemporalCursor();
  useEffect(() => {
    setTemporalCapabilities({
      defaultScope: {
        txAt: "2026-04-16T00:00:00Z",
        validAt: "2026-04-15T00:00:00Z",
      },
      eventPoints: [
        {
          id: "start",
          kind: "run_start",
          label: "start",
          timestamp: "2026-04-10T00:00:00Z",
        },
        {
          id: "finish",
          kind: "run_finish",
          label: "finish",
          timestamp: "2026-04-20T00:00:00Z",
        },
      ],
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
  }, [setTemporalCapabilities]);

  return (
    <TemporalScrubber
      labels={{
        now: "Now",
        observed: "Observed",
        simulated: "Simulated",
        slider: "Temporal cursor",
      }}
    />
  );
}

function renderScrubber() {
  const queryClient = createTestQueryClient();
  function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <ReducedMotionProvider>
            <TemporalCursorProvider>{children}</TemporalCursorProvider>
          </ReducedMotionProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(<TemporalHarness />, { wrapper: Wrapper });
}

describe("TemporalScrubber", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("updates preview on change and commits after debounce", () => {
    renderScrubber();
    const slider = screen.getByRole("slider", { name: "Temporal cursor" });

    fireEvent.change(slider, {
      target: { value: new Date("2026-04-18T00:00:00Z").getTime() },
    });
    act(() => {
      vi.advanceTimersByTime(16);
      vi.advanceTimersByTime(150);
    });

    expect(window.location.search).toContain("valid_at=2026-04-18");
  });

  it("supports keyboard navigation and now action", () => {
    renderScrubber();
    const slider = screen.getByRole("slider", { name: "Temporal cursor" });

    fireEvent.keyDown(slider, { key: "Home" });
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(window.location.search).toContain("valid_at=2026-04-10");

    fireEvent.click(screen.getByRole("button", { name: "Now" }));
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(window.location.search).toContain("valid_at=2026-04-20");
  });
});
