import { act, renderHook } from "@testing-library/react";

import { useWorker } from "./useWorker";

type MockWorker<Message> = {
  onerror: ((error: ErrorEvent) => void) | null;
  onmessage: ((event: MessageEvent<Message>) => void) | null;
  postMessage: ReturnType<typeof vi.fn>;
  terminate: ReturnType<typeof vi.fn>;
};

function createMockWorker<Message>(): MockWorker<Message> {
  return {
    onerror: null,
    onmessage: null,
    postMessage: vi.fn(),
    terminate: vi.fn(),
  };
}

describe("useWorker", () => {
  it("delivers worker messages to the latest callback after rerender", () => {
    const worker = createMockWorker<string>();
    const createWorker = vi.fn(
      () => worker as unknown as Worker & { postMessage(message: string): void },
    );
    const initialHandler = vi.fn();
    const updatedHandler = vi.fn();

    const view = renderHook(
      ({ handler }: { handler: (message: string) => void }) =>
        useWorker(createWorker, handler),
      {
        initialProps: { handler: initialHandler },
      },
    );

    view.rerender({ handler: updatedHandler });

    act(() => {
      worker.onmessage?.({ data: "updated" } as MessageEvent<string>);
    });

    expect(initialHandler).not.toHaveBeenCalled();
    expect(updatedHandler).toHaveBeenCalledWith("updated");
  });
});
