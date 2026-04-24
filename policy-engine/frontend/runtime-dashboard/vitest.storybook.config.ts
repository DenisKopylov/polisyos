import path from "node:path";

import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    storybookTest({ configDir: path.resolve(__dirname, ".storybook") }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "virtual:pwa-register": path.resolve(
        __dirname,
        "./.storybook/mocks/virtual-pwa-register.ts",
      ),
    },
  },
  optimizeDeps: {
    include: [
      "@storybook/react-vite",
      "@storybook/addon-a11y/preview",
      "@tanstack/react-query",
      "@hookform/resolvers/zod",
      "idb",
      "react-router-dom",
      "react-dom/client",
      "react-hook-form",
      "web-vitals",
    ],
  },
  test: {
    name: "storybook",
    globals: true,
    css: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    setupFiles: ["./.storybook/vitest.setup.ts"],
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium" }],
    },
  },
});
