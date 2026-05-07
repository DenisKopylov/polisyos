"use strict";

const { RuleTester } = require("eslint");
const rule = require("./quantity-must-be-wrapped.cjs");

RuleTester.setDefaultConfig({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    parserOptions: {
      ecmaFeatures: { jsx: true },
    },
  },
});

const tester = new RuleTester();

tester.run("quantity-must-be-wrapped", rule, {
  valid: [
    {
      code: "const view = <Quantity value={quantity} />;",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const view = <Icon size={16} />;",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const durationMs = /* policyos-quantity: telemetry */ 42;",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const latencyMs = 25;",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const visible = items.slice(0, 4);",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const view = <span>{items.length > 0 ? value.toFixed(2) : '-'}</span>;",
      filename: "src/features/example/View.tsx",
    },
    {
      code: "const view = <span>{42}</span>;",
      filename: "src/features/example/View.test.tsx",
    },
  ],
  invalid: [
    {
      code: "const view = <span>{0.23}</span>;",
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
    {
      code: "const confidenceScore = 0.92;",
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
    {
      code: "const latencyMs = 25;",
      filename: "src/features/example/View.tsx",
      options: [{ classes: ["telemetry"] }],
      errors: [{ messageId: "telemetry" }],
    },
  ],
});
