import globals from "globals";
import { createRequire } from "node:module";
import tseslint from "typescript-eslint";

const require = createRequire(import.meta.url);
const localPlugin = require("./eslint-plugin-local/index.cjs");

export default [
  {
    ignores: [
      "**/coverage/**",
      "**/dist/**",
      "**/node_modules/**",
      "**/storybook-static/**",
      "**/test-results/**",
      "**/.tmp/**",
      "src/api/types.ts",
      "src/**/*.test.{ts,tsx}",
      "src/**/*.a11y.test.{ts,tsx}",
      "src/**/*.stories.{ts,tsx}",
      "src/**/__fixtures__/**",
      "src/**/fixtures/**",
      "src/test/**",
    ],
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parser: tseslint.parser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
        sourceType: "module",
      },
    },
    plugins: {
      policyos: localPlugin,
    },
    rules: {
      "policyos/quantity-must-be-wrapped": [
        "error",
        { classes: ["decision"] },
      ],
    },
  },
];
