import { act, renderHook } from "@testing-library/react";

import { useTouchGestures } from "./useTouchGestures";

describe("useTouchGestures", () => {
  it("uses the latest swipe handler after rerender", () => {
    const initialSwipe = vi.fn();
    const updatedSwipe = vi.fn();
    const ref = { current: document.createElement("div") };

    const view = renderHook(
      ({ onSwipe }: { onSwipe: (direction: string) => void }) =>
        useTouchGestures(ref, {
          onSwipe: (direction) => onSwipe(direction),
        }),
      {
        initialProps: { onSwipe: initialSwipe },
      },
    );

    view.rerender({ onSwipe: updatedSwipe });

    act(() => {
      view.result.current.onTouchStart({
        touches: [{ clientX: 10, clientY: 10 }],
      } as unknown as React.TouchEvent);
      view.result.current.onTouchEnd({
        changedTouches: [{ clientX: 120, clientY: 10 }],
      } as unknown as React.TouchEvent);
    });

    expect(initialSwipe).not.toHaveBeenCalled();
    expect(updatedSwipe).toHaveBeenCalledWith("right");
  });
});
