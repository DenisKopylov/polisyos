import type { PropsWithChildren } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReducedMotionProvider } from "@/shared/a11y";
import {
  TemporalRuntimeBridgeProvider,
  type TemporalRuntimeBridgeValue,
} from "./TemporalRuntimeBridge";
import { TemporalScrubber } from "./TemporalScrubber";

const RANGE = {
  earliest: "2026-04-10T00:00:00Z",
  latest: "2026-04-20T00:00:00Z",
};

function renderScrubber() {
  const commitScope = vi.fn();
  const value: TemporalRuntimeBridgeValue = {
    capabilities: {
      defaultScope: {
        txAt: "2026-04-16T00:00:00Z",
        validAt: "2026-04-15T00:00:00Z",
      },
      eventPoints: [
        {
          id: "start",
          kind: "run_start",
          label: "start",
          timestamp: RANGE.earliest,
        },
        {
          id: "finish",
          kind: "run_finish",
          label: "finish",
          timestamp: RANGE.latest,
        },
      ],
      resolution: "event",
      runId: "run-1",
      surfaces: [],
      txRange: RANGE,
      validRange: RANGE,
    },
    committedScope: null,
    commitPreview: vi.fn(),
    commitScope,
    effectiveScope: {
      txAt: "2026-04-16T00:00:00Z",
      validAt: "2026-04-15T00:00:00Z",
    },
    eventPoints: [],
    previewScope: null,
    range: RANGE,
    resetScope: vi.fn(),
    setPreviewScope: vi.fn(),
    setTemporalCapabilities: vi.fn(),
    stepValidTime: vi.fn(),
    txRange: RANGE,
  };

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <ReducedMotionProvider>
        <TemporalRuntimeBridgeProvider value={value}>
          {children}
        </TemporalRuntimeBridgeProvider>
      </ReducedMotionProvider>
    );
  }

  return {
    commitScope,
    ...render(
      <TemporalScrubber
        labels={{
          now: "Now",
          observed: "Observed",
          simulated: "Simulated",
          slider: "Temporal cursor",
        }}
      />,
      { wrapper: Wrapper },
    ),
  };
}

describe("TemporalScrubber", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("updates preview on change and commits after debounce", () => {
    const { commitScope } = renderScrubber();
    const slider = screen.getByRole("slider", { name: "Temporal cursor" });

    fireEvent.change(slider, {
      target: { value: new Date("2026-04-18T00:00:00Z").getTime() },
    });
    act(() => {
      vi.advanceTimersByTime(16);
      vi.advanceTimersByTime(150);
    });

    expect(commitScope).toHaveBeenCalledWith(
      expect.objectContaining({ validAt: "2026-04-18T00:00:00.000Z" }),
    );
  });

  it("supports keyboard navigation and now action", () => {
    const { commitScope } = renderScrubber();
    const slider = screen.getByRole("slider", { name: "Temporal cursor" });

    fireEvent.keyDown(slider, { key: "Home" });
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(commitScope).toHaveBeenCalledWith(
      expect.objectContaining({ validAt: "2026-04-10T00:00:00.000Z" }),
    );

    commitScope.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Now" }));
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(commitScope).toHaveBeenCalledWith(
      expect.objectContaining({ validAt: "2026-04-20T00:00:00.000Z" }),
    );
  });
});
