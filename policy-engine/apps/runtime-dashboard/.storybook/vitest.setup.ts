import "@testing-library/jest-dom/vitest";
import { beforeAll } from "vitest";
import { setProjectAnnotations } from "@storybook/react-vite";
import * as a11yAddonAnnotations from "@storybook/addon-a11y/preview";

import * as previewAnnotations from "./preview";

if (typeof globalThis.window !== "undefined" && !globalThis.window.matchMedia) {
  Object.defineProperty(globalThis.window, "matchMedia", {
    value: (query: string) => ({
      addEventListener: () => undefined,
      addListener: () => undefined,
      dispatchEvent: () => false,
      matches: query.includes("dark"),
      media: query,
      onchange: null,
      removeEventListener: () => undefined,
      removeListener: () => undefined,
    }),
    writable: true,
  });
}

if (typeof globalThis.window !== "undefined") {
  globalThis.window.__RUNTIME_DASHBOARD_TEST__ = true;
}

const annotations = setProjectAnnotations([
  a11yAddonAnnotations,
  previewAnnotations,
]);

beforeAll(annotations.beforeAll);
