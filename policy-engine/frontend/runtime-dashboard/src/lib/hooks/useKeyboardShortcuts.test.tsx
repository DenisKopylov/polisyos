import { act, renderHook } from "@testing-library/react";

import { useGlobalShortcut } from "./useKeyboardShortcuts";

describe("useGlobalShortcut", () => {
  it("invokes the latest handler after rerender", () => {
    const initialHandler = vi.fn();
    const updatedHandler = vi.fn();

    const view = renderHook(
      ({ handler }: { handler: () => void }) =>
        useGlobalShortcut(
          "test-shortcut",
          { key: "k", meta: true },
          "Open test palette",
          handler,
        ),
      {
        initialProps: { handler: initialHandler },
      },
    );

    view.rerender({ handler: updatedHandler });

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "k",
          metaKey: true,
        }),
      );
    });

    expect(initialHandler).not.toHaveBeenCalled();
    expect(updatedHandler).toHaveBeenCalledTimes(1);

    view.unmount();
  });
});
