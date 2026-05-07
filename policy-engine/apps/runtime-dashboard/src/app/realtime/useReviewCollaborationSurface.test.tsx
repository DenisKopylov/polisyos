import { useRef } from "react";
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";
import { useReviewCollaborationSurface } from "./useReviewCollaborationSurface";

const subscribeMock = vi.fn();

vi.mock("@/app/realtime/realtimeClient", () => ({
  getRealtimeClient: () => ({
    subscribe: subscribeMock,
  }),
}));

function SurfaceProbe() {
  const ref = useRef<HTMLButtonElement>(null);
  useReviewCollaborationSurface({
    enabled: true,
    reviewId: "review-1",
    runId: "run-1",
    surfaceRef: ref,
  });

  return (
    <button ref={ref} data-testid="review-surface" type="button">
      review surface
    </button>
  );
}

describe("useReviewCollaborationSurface", () => {
  beforeEach(() => {
    subscribeMock.mockReset();
  });

  it("throttles cursor updates and avoids layout reads on every mouse move", () => {
    const sendByChannel = new Map<string, ReturnType<typeof vi.fn>>();
    const frameQueue: FrameRequestCallback[] = [];

    subscribeMock.mockImplementation((request, handlers) => {
      const send = vi.fn();
      sendByChannel.set(request.channel, send);
      if (request.channel === "review.presence") {
        handlers.onOpen?.(new Event("open"));
      }
      return { close: vi.fn(), send };
    });
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      frameQueue.push(callback);
      return frameQueue.length;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(
      () => undefined,
    );

    const rectSpy = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockReturnValue({
        bottom: 100,
        height: 100,
        left: 0,
        right: 100,
        top: 0,
        width: 100,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect);

    renderWithProviders(<SurfaceProbe />);

    const surface = screen.getByTestId("review-surface");
    fireEvent.mouseEnter(surface);

    const rectCallsAfterEnter = rectSpy.mock.calls.length;
    const cursorSend = sendByChannel.get("review.cursor");
    const lockSend = sendByChannel.get("review.lock");

    expect(lockSend).toHaveBeenCalledWith({ type: "lock.acquire" });

    fireEvent.mouseMove(surface, { clientX: 40, clientY: 50 });
    frameQueue.shift()?.(16);
    fireEvent.mouseMove(surface, { clientX: 40, clientY: 50 });
    frameQueue.shift()?.(32);
    fireEvent.mouseMove(surface, { clientX: 80, clientY: 70 });
    frameQueue.shift()?.(48);

    expect(cursorSend).toHaveBeenCalledTimes(2);
    expect(cursorSend).toHaveBeenNthCalledWith(1, {
      type: "cursor.update",
      x: 0.4,
      y: 0.5,
    });
    expect(cursorSend).toHaveBeenNthCalledWith(2, {
      type: "cursor.update",
      x: 0.8,
      y: 0.7,
    });
    expect(rectSpy.mock.calls.length).toBe(rectCallsAfterEnter);
  });
});
