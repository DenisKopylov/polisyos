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
    {
      name: "accepts aliased canonical SVG geometry",
      code: `
        import { layoutGeometry as geometry } from "@/shared/lib/domain/nonAuthorityNumeric";
        const view = <rect x={geometry(-24)} y={geometry(-9)} />;
      `,
      filename: "src/features/example/View.tsx",
    },
    {
      name: "accepts a typed operational request control",
      code: `
        import { operationalRequestControl } from "@/shared/lib/domain/nonAuthorityNumeric";
        const payload = { cost_budget_usd: operationalRequestControl(0) };
      `,
      filename: "src/features/example/View.tsx",
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
    {
      name: "rejects decision values disguised as layout or motion",
      code: `
        import { layoutGeometry, motionGeometry } from "@/shared/lib/domain/nonAuthorityNumeric";
        const effect = layoutGeometry(0.23);
        const confidence = motionGeometry(0.92);
      `,
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }, { messageId: "decision" }],
    },
    {
      name: "accepts structurally typed SVG geometry without exempting numeric effect values",
      code: `
        import { layoutGeometry } from "@/shared/lib/domain/nonAuthorityNumeric";
        const view = <rect x={layoutGeometry(-24)} y={layoutGeometry(-9)} />;
        const effect = layoutGeometry(0.23);
      `,
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
    {
      name: "rejects a canonical classification in a rendered decision slot",
      code: `
        import { layoutGeometry } from "@/shared/lib/domain/nonAuthorityNumeric";
        const view = <span>{layoutGeometry(0.23)}</span>;
      `,
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
    {
      name: "rejects a same-named local classification function",
      code: `
        const layoutGeometry = (value) => value;
        const view = <span>{layoutGeometry(0.23)}</span>;
      `,
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
    {
      name: "rejects a local function shadowing a canonical classifier alias",
      code: `
        import { layoutGeometry as geometry } from "@/shared/lib/domain/nonAuthorityNumeric";
        function renderCandidate() {
          const geometry = (value) => value;
          return <rect x={geometry(-24)} />;
        }
      `,
      filename: "src/features/example/View.tsx",
      errors: [{ messageId: "decision" }],
    },
  ],
});
