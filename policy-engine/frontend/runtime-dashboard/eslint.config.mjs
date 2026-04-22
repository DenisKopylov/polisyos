import js from "@eslint/js";
import vitest from "@vitest/eslint-plugin";
import boundaries from "eslint-plugin-boundaries";
import eslintConfigPrettier from "eslint-config-prettier";
import importPlugin from "eslint-plugin-import";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import storybook from "eslint-plugin-storybook";
import testingLibrary from "eslint-plugin-testing-library";
import unusedImports from "eslint-plugin-unused-imports";
import globals from "globals";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import tseslint from "typescript-eslint";

const require = createRequire(import.meta.url);
const localPlugin = require("./eslint-plugin-local/index.cjs");

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const appFiles = ["src/**/*.{ts,tsx}"];
const testFiles = ["src/**/*.test.{ts,tsx}", "src/**/*.a11y.test.{ts,tsx}"];
const e2eFiles = ["e2e/**/*.ts"];
const storyFiles = ["src/**/*.stories.{ts,tsx}"];
const toolingFiles = [
  "*.config.{js,mjs,ts}",
  ".storybook/**/*.{ts,tsx}",
  "scripts/**/*.{mjs,ts}",
  "e2e/**/*.ts",
];

export default tseslint.config(
  {
    ignores: [
      "**/coverage/**",
      "**/dist/**",
      "**/node_modules/**",
      "**/storybook-static/**",
      "**/test-results/**",
      "**/.tmp/**",
      ".eslintcache",
      "src/api/types.ts",
    ],
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
  js.configs.recommended,
  {
    files: appFiles,
    extends: [
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
      importPlugin.flatConfigs.recommended,
      importPlugin.flatConfigs.typescript,
      jsxA11y.flatConfigs.strict,
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        project: ["./tsconfig.eslint.json"],
        tsconfigRootDir: rootDir,
      },
    },
    plugins: {
      boundaries,
      local: localPlugin,
      "testing-library": testingLibrary,
      "unused-imports": unusedImports,
    },
    settings: {
      "import/resolver": {
        typescript: {
          project: "./tsconfig.eslint.json",
        },
      },
      "boundaries/elements": [
        { type: "app", pattern: "src/app/**" },
        { type: "api", pattern: "src/api/**" },
        { type: "feature", pattern: "src/features/*/**" },
        { type: "shared", pattern: "src/shared/**" },
        { type: "lib", pattern: "src/lib/**" },
        { type: "i18n", pattern: "src/i18n/**" },
      ],
    },
    rules: {
      "boundaries/element-types": "off",
      "boundaries/no-ignored": "off",
      "boundaries/no-private": "off",
      "boundaries/no-unknown": "off",
      "boundaries/no-unknown-files": "off",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        {
          prefer: "type-imports",
        },
      ],
      "@typescript-eslint/no-confusing-void-expression": [
        "error",
        {
          ignoreArrowShorthand: true,
        },
      ],
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/consistent-indexed-object-style": "off",
      "@typescript-eslint/no-misused-promises": [
        "error",
        {
          checksVoidReturn: {
            attributes: false,
          },
        },
      ],
      "@typescript-eslint/array-type": "off",
      "@typescript-eslint/consistent-type-definitions": "off",
      "@typescript-eslint/no-base-to-string": "off",
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/only-throw-error": "off",
      "@typescript-eslint/no-unnecessary-type-assertion": "off",
      "@typescript-eslint/no-unnecessary-type-conversion": "off",
      "@typescript-eslint/non-nullable-type-assertion-style": "off",
      "@typescript-eslint/no-unnecessary-condition": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/prefer-nullish-coalescing": "off",
      "@typescript-eslint/prefer-optional-chain": "off",
      "@typescript-eslint/prefer-regexp-exec": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "import/no-cycle": "error",
      "import/no-default-export": "off",
      "import/no-duplicates": "error",
      "import/no-unresolved": "off",
      "import/order": "off",
      "no-extra-boolean-cast": "off",
      "no-console": [
        "error",
        {
          allow: ["error", "warn"],
        },
      ],
      "react-hooks/exhaustive-deps": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/set-state-in-effect": "off",
      "unused-imports/no-unused-imports": "error",
      "local/no-raw-emoji-in-jsx": "error",
    },
  },
  {
    files: testFiles,
    extends: [testingLibrary.configs["flat/react"], vitest.configs.recommended],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...vitest.environments.env.globals,
      },
    },
    rules: {
      "@typescript-eslint/consistent-type-imports": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/unbound-method": "off",
      "no-console": "off",
      "testing-library/render-result-naming-convention": "off",
      "vitest/expect-expect": [
        "error",
        {
          assertFunctionNames: ["expect", "expectNoA11yViolations"],
        },
      ],
    },
  },
  {
    files: e2eFiles,
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "no-console": "off",
      "no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
        },
      ],
    },
  },
  {
    files: ["src/shared/telemetry/logger.ts"],
    rules: {
      "no-console": "off",
    },
  },
  {
    files: storyFiles,
    extends: [...storybook.configs["flat/recommended"]],
    rules: {
      "import/no-anonymous-default-export": "off",
    },
  },
  {
    files: toolingFiles,
    languageOptions: {
      globals: {
        ...globals.node,
      },
      parser: tseslint.parser,
    },
    rules: {
      "no-console": "off",
    },
  },
  eslintConfigPrettier,
);
