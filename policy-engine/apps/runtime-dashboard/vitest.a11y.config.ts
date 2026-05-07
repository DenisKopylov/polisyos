import { defineConfig, mergeConfig } from "vitest/config";

import baseConfig from "./vitest.config";

export default mergeConfig(
  baseConfig,
  defineConfig({
    test: {
      include: ["src/shared/ui/**/*.a11y.test.tsx"],
    },
  }),
);
