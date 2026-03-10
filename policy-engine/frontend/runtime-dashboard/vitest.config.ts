import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary", "lcov"],
      include: [
        "src/api/hooks/**/*.{ts,tsx}",
        "src/app/layout/**/*.{ts,tsx}",
        "src/features/artifacts/routes/**/*.{ts,tsx}",
        "src/features/auth/routes/**/*.{ts,tsx}",
        "src/features/composer/**/*.{ts,tsx}",
        "src/features/dashboard/routes/**/*.{ts,tsx}",
        "src/features/evidence/**/*.{ts,tsx}",
        "src/features/lex/routes/**/*.{ts,tsx}",
        "src/features/platform/routes/**/*.{ts,tsx}",
        "src/features/runs/**/*.{ts,tsx}",
        "src/shared/components/**/*.{ts,tsx}",
        "src/shared/ui/**/*.{ts,tsx}",
      ],
      exclude: [
        "src/**/*.stories.{ts,tsx}",
        "src/**/*.test.{ts,tsx}",
        "src/**/*.a11y.test.{ts,tsx}",
        "src/**/index.ts",
        "src/**/route.tsx",
        "src/test/**",
      ],
    },
  },
});
