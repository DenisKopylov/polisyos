import { beforeEach, describe, expect, it, vi } from "vitest";

import { exportElementAsImage } from "./printExport";

describe("exportElementAsImage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("rasterizes the element into a real PNG download", async () => {
    const element = document.createElement("div");
    element.textContent = "Export me";
    document.body.appendChild(element);

    vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
      bottom: 50,
      height: 50,
      left: 0,
      right: 120,
      top: 0,
      width: 120,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRect);

    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      clearRect: vi.fn(),
      drawImage,
      scale: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
      (callback) => {
        callback(new Blob(["png"], { type: "image/png" }));
      },
    );

    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    vi.spyOn(URL, "createObjectURL")
      .mockReturnValueOnce("blob:svg")
      .mockReturnValueOnce("blob:png");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    const originalImage = globalThis.Image;
    class MockImage {
      decoding = "async";
      onerror: null | (() => void) = null;
      onload: null | (() => void) = null;

      set src(_value: string) {
        this.onload?.();
      }
    }
    globalThis.Image = MockImage as unknown as typeof Image;

    try {
      await exportElementAsImage(element, "snapshot.png");

      expect(drawImage).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalledTimes(1);
    } finally {
      globalThis.Image = originalImage;
      element.remove();
    }
  });
});
