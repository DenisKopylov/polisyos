import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

if (typeof HTMLCanvasElement !== "undefined") {
  Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
    value: vi.fn(() => null),
    writable: true,
  });
}
