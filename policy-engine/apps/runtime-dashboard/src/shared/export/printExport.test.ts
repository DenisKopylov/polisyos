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

  it("inherits epoch semantics from the source DOM instead of reconstructing them", async () => {
    const element = document.createElement("div");
    element.dataset.renderRoot = "decision-bearing";
    element.innerHTML =
      '<span data-epoch-status="stale">Epoch epoch-17 · stale</span>';
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
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      clearRect: vi.fn(),
      drawImage: vi.fn(),
      scale: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
      (callback) => {
        callback(new Blob(["png"], { type: "image/png" }));
      },
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );

    const rasterInputs: Blob[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      if (
        value instanceof Blob &&
        value.type === "image/svg+xml;charset=utf-8"
      ) {
        rasterInputs.push(value);
      }
      return `blob:${rasterInputs.length}`;
    });
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
      await exportElementAsImage(element, "stale.png");
      element.querySelector("[data-epoch-status]")?.remove();
      await exportElementAsImage(element, "without-epoch.png");

      expect(rasterInputs).toHaveLength(2);
      expect(await readBlobText(rasterInputs[0])).toContain(
        'data-epoch-status="stale"',
      );
      expect(await readBlobText(rasterInputs[1])).not.toContain(
        "data-epoch-status",
      );
    } finally {
      globalThis.Image = originalImage;
      element.remove();
    }
  });
});

function readBlobText(blob: Blob | undefined): Promise<string> {
  if (!blob) {
    return Promise.reject(new Error("expected a raster input blob"));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("blob read failed"));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
}
