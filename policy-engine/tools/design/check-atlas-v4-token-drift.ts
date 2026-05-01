import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

type ThemeName = "dark" | "light";

type TokenMap = Record<string, string>;

const POLICY_ENGINE_ROOT = getPolicyEngineRoot();
const REFERENCE_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "docs/brand/atlas-v4/colors_and_type.css",
);
const ADOPTION_DOC_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "docs/brand/ATLAS_V4_ADOPTION.md",
);
const DESIGN_SYSTEM_DOC_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "docs/brand/ATLAS_DESIGN_SYSTEM.md",
);
const DARK_THEME_ADR_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "docs/adr/ADR-047-atlas-v4-dark-theme-canonicalization.md",
);
const STORYBOOK_REFERENCE_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "frontend/runtime-dashboard/src/shared/ui/tokens/AtlasV4Reference.stories.tsx",
);
const PACKAGE_JSON_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "frontend/runtime-dashboard/package.json",
);
const STYLES_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "frontend/runtime-dashboard/src/styles.css",
);
const LIGHT_THEME_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "frontend/runtime-dashboard/src/styles/theme-light.css",
);
const DARK_THEME_PATH = path.join(
  POLICY_ENGINE_ROOT,
  "frontend/runtime-dashboard/src/styles/theme-dark.css",
);

const allowedDifferences = new Map<string, string>();

function allow(themes: ThemeName[], tokens: string[], decision: string) {
  for (const theme of themes) {
    for (const token of tokens) {
      allowedDifferences.set(`${theme}:${token}`, decision);
    }
  }
}

allow(
  ["light"],
  ["--panel", "--panel-strong", "--surface"],
  "D01 light glass contrast",
);

allow(["light"], ["--chart-secondary"], "D02 no blue signal color");

allow(
  ["light"],
  [
    "--color-ci-50",
    "--color-ci-80",
    "--color-ci-95",
    "--color-bounds-fill",
    "--color-bounds-stroke",
  ],
  "D03 theme-aware confidence bands",
);

allow(
  ["light"],
  [
    "--color-waterfall-positive",
    "--color-waterfall-negative",
    "--color-waterfall-total",
  ],
  "D04 semantic waterfall aliases",
);

allow(
  ["dark", "light"],
  [
    "--space-1",
    "--space-2",
    "--space-3",
    "--space-4",
    "--space-5",
    "--space-6",
    "--space-7",
    "--space-8",
  ],
  "D05 density-aware spacing",
);

allow(["dark", "light"], ["--radius-card"], "D06 card radius contract");
allow(["dark", "light"], ["--radius-shell"], "D07 shell radius reference");
allow(
  ["dark", "light"],
  ["--shadow-panel", "--rim-light"],
  "D08 shadow aliases",
);

allow(["dark", "light"], ["--font-serif"], "D09 serif is component-scoped");

allow(
  ["dark", "light"],
  ["--text-5xl", "--text-display"],
  "D10 display type is reference-only",
);

allow(
  ["dark", "light"],
  ["--tracking-tighter", "--tracking-tight", "--tracking-snug"],
  "D11 production tracking",
);

allow(
  ["dark"],
  [
    "--paper",
    "--sand",
    "--ink",
    "--graphite",
    "--slate",
    "--line",
    "--canvas",
    "--teal",
    "--ember",
    "--gold",
    "--teal-soft",
    "--ember-soft",
    "--gold-soft",
    "--panel",
    "--panel-strong",
    "--surface",
    "--shell-border",
    "--shell-glass-start",
    "--shell-glass-end",
    "--shell-glass-base",
    "--page-gradient-start",
    "--page-gradient-mid",
    "--page-gradient-end",
    "--page-glow-teal",
    "--page-glow-ember",
  ],
  "D12 warm dark palette",
);

allow(
  ["dark"],
  [
    "--accent",
    "--success",
    "--warning",
    "--danger",
    "--button-primary-start",
    "--button-primary-end",
    "--button-primary-text",
    "--chart-grid",
    "--chart-axis",
    "--chart-primary",
    "--chart-alert",
    "--chart-neutral",
    "--chart-secondary",
    "--color-governance-review",
    "--color-ci-50",
    "--color-ci-80",
    "--color-ci-95",
    "--color-bounds-fill",
    "--color-bounds-stroke",
    "--color-confidence-high",
    "--color-confidence-medium",
    "--color-confidence-low",
    "--color-waterfall-positive",
    "--color-waterfall-negative",
    "--color-waterfall-total",
    "--rail-active-bg",
    "--rail-hover-bg",
    "--rail-link",
    "--focus-ring",
    "--shadow-panel",
    "--rim-light",
  ],
  "D13 warm dark semantic recalibration",
);

function readFile(filePath: string) {
  return fs.readFileSync(filePath, "utf8");
}

function assertRequiredArtifactsExist() {
  const requiredArtifacts = [
    ["Atlas v4 reference tokens", REFERENCE_PATH],
    ["Atlas design-system doc", DESIGN_SYSTEM_DOC_PATH],
    ["Atlas v4 adoption record", ADOPTION_DOC_PATH],
    ["Atlas v4 dark-theme ADR", DARK_THEME_ADR_PATH],
    ["Atlas v4 Storybook reference", STORYBOOK_REFERENCE_PATH],
    ["runtime dashboard package.json", PACKAGE_JSON_PATH],
    ["runtime dashboard base styles", STYLES_PATH],
    ["runtime dashboard light theme", LIGHT_THEME_PATH],
    ["runtime dashboard dark theme", DARK_THEME_PATH],
  ] as const;

  return requiredArtifacts
    .filter(([, artifactPath]) => !fs.existsSync(artifactPath))
    .map(
      ([label, artifactPath]) =>
        `${label} is missing at ${path.relative(POLICY_ENGINE_ROOT, artifactPath)}`,
    );
}

function assertContains(
  source: string,
  needle: string,
  label: string,
  failures: string[],
) {
  if (!source.includes(needle)) {
    failures.push(`${label} must mention ${needle}`);
  }
}

function assertDocumentationContract() {
  const failures: string[] = [];
  const designDoc = readFile(DESIGN_SYSTEM_DOC_PATH);
  const adoptionDoc = readFile(ADOPTION_DOC_PATH);
  const darkThemeAdr = readFile(DARK_THEME_ADR_PATH);

  for (const needle of [
    "docs/brand/atlas-v4/colors_and_type.css",
    "docs/brand/ATLAS_V4_ADOPTION.md",
    "ADR-047",
    "design:atlas-v4",
    "AtlasV4Reference.stories.tsx",
  ]) {
    assertContains(designDoc, needle, "ATLAS_DESIGN_SYSTEM.md", failures);
  }

  for (const needle of [
    "docs/brand/atlas-v4/colors_and_type.css",
    "docs/brand/ATLAS_DESIGN_SYSTEM.md",
    "docs/adr/ADR-047-atlas-v4-dark-theme-canonicalization.md",
    "src/shared/ui/tokens/AtlasV4Reference.stories.tsx",
    "design:atlas-v4",
  ]) {
    assertContains(adoptionDoc, needle, "ATLAS_V4_ADOPTION.md", failures);
  }

  for (const needle of [
    "warm dark theme as canonical",
    "docs/brand/ATLAS_V4_ADOPTION.md",
    "tools/design/check-atlas-v4-token-drift.ts",
  ]) {
    assertContains(
      darkThemeAdr,
      needle,
      "ADR-047-atlas-v4-dark-theme-canonicalization.md",
      failures,
    );
  }

  return failures;
}

function assertStorybookReferenceContract() {
  const storySource = readFile(STORYBOOK_REFERENCE_PATH);
  const failures: string[] = [];

  for (const exportName of [
    "Color",
    "ColorDark",
    "Type",
    "Shadows",
    "Glyphs",
    "Buttons",
    "Badges",
    "Cards",
  ]) {
    assertContains(
      storySource,
      `export const ${exportName}: Story`,
      "AtlasV4Reference.stories.tsx",
      failures,
    );
  }

  for (const componentName of [
    "AtlasBrand",
    "Glyph",
    "Button",
    "Badge",
    "Card",
    "MetricCard",
  ]) {
    assertContains(
      storySource,
      componentName,
      "AtlasV4Reference.stories.tsx",
      failures,
    );
  }

  return failures;
}

function assertPackageScripts() {
  const packageJson = JSON.parse(readFile(PACKAGE_JSON_PATH)) as {
    scripts?: Record<string, string>;
  };
  const scripts = packageJson.scripts ?? {};
  const failures: string[] = [];

  if (
    scripts["design:atlas-v4"] !==
    "node --experimental-strip-types ../../tools/design/check-atlas-v4-token-drift.ts"
  ) {
    failures.push(
      "package.json must define the canonical design:atlas-v4 script",
    );
  }

  if (!scripts["design:polish"]?.includes("npm run design:atlas-v4")) {
    failures.push("package.json design:polish must run design:atlas-v4 first");
  }

  return failures;
}

function extractCssBlocks(source: string, selector: string) {
  const blocks: string[] = [];
  let cursor = 0;

  while (cursor < source.length) {
    const selectorIndex = source.indexOf(selector, cursor);

    if (selectorIndex === -1) {
      break;
    }

    const nextCharacter = source[selectorIndex + selector.length] ?? "";
    if (selector === ":root" && nextCharacter === "[") {
      cursor = selectorIndex + selector.length;
      continue;
    }

    const openBraceIndex = source.indexOf("{", selectorIndex);
    if (openBraceIndex === -1) {
      break;
    }

    const selectorText = source.slice(selectorIndex, openBraceIndex);
    if (selector === ":root" && selectorText.includes("[data-theme")) {
      cursor = openBraceIndex + 1;
      continue;
    }

    let depth = 0;
    for (let index = openBraceIndex; index < source.length; index += 1) {
      const character = source[index];
      if (character === "{") {
        depth += 1;
      }
      if (character === "}") {
        depth -= 1;
        if (depth === 0) {
          blocks.push(source.slice(openBraceIndex + 1, index));
          cursor = index + 1;
          break;
        }
      }
    }

    if (depth !== 0) {
      break;
    }
  }

  return blocks;
}

function parseCssVariables(source: string): TokenMap {
  const variables: TokenMap = {};
  const matches = source.matchAll(/(--[\w-]+)\s*:\s*([\s\S]*?);/g);

  for (const match of matches) {
    variables[match[1]] = normalizeValue(match[2]);
  }

  return variables;
}

function normalizeValue(value: string) {
  return value
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\s+/g, " ")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/\s*,\s*/g, ", ")
    .trim()
    .replace(/#[0-9a-fA-F]+/g, (hex) => hex.toLowerCase());
}

function loadReferenceTokens(css: string) {
  const light = parseCssVariables(extractCssBlocks(css, ":root").join("\n"));
  const dark = {
    ...light,
    ...parseCssVariables(
      extractCssBlocks(css, '[data-theme="dark"]').join("\n"),
    ),
  };

  return { dark, light };
}

function loadProductionTokens() {
  const baseCss = readFile(STYLES_PATH);
  const lightCss = readFile(LIGHT_THEME_PATH);
  const darkCss = readFile(DARK_THEME_PATH);
  const light = parseCssVariables(`${baseCss}\n${lightCss}`);
  const dark = parseCssVariables(`${baseCss}\n${lightCss}\n${darkCss}`);

  return { dark, light };
}

function formatFailure(
  theme: ThemeName,
  token: string,
  expected: string,
  actual?: string,
) {
  if (actual === undefined) {
    return `${theme}:${token} missing in production; reference=${expected}`;
  }

  return `${theme}:${token} drifted; reference=${expected}; production=${actual}`;
}

function assertAllowedDecisionsAreDocumented() {
  const adoptionDoc = readFile(ADOPTION_DOC_PATH);
  const failures: string[] = [];

  for (const [key, decision] of allowedDifferences) {
    const token = key.split(":")[1];
    if (!adoptionDoc.includes(token)) {
      failures.push(
        `${key} is allowlisted by ${decision} but missing from docs`,
      );
    }
  }

  return failures;
}

const artifactFailures = assertRequiredArtifactsExist();
const failures: string[] = [...artifactFailures];
let comparedCount = 0;
let acceptedDifferenceCount = 0;

if (artifactFailures.length === 0) {
  failures.push(
    ...assertDocumentationContract(),
    ...assertStorybookReferenceContract(),
    ...assertPackageScripts(),
    ...assertAllowedDecisionsAreDocumented(),
  );

  const referenceTokens = loadReferenceTokens(readFile(REFERENCE_PATH));
  const productionTokens = loadProductionTokens();

  for (const theme of ["light", "dark"] as const) {
    const reference = referenceTokens[theme];
    const production = productionTokens[theme];

    for (const token of Object.keys(reference).sort()) {
      const key = `${theme}:${token}`;
      const expected = reference[token];
      const actual = production[token];

      comparedCount += 1;

      if (actual === undefined) {
        if (allowedDifferences.has(key)) {
          acceptedDifferenceCount += 1;
          continue;
        }
        failures.push(formatFailure(theme, token, expected));
        continue;
      }

      if (normalizeValue(actual) !== normalizeValue(expected)) {
        if (allowedDifferences.has(key)) {
          acceptedDifferenceCount += 1;
          continue;
        }
        failures.push(formatFailure(theme, token, expected, actual));
      }
    }
  }
}

if (failures.length > 0) {
  throw new Error(
    [
      "Atlas v4 token drift check failed.",
      "Every mismatch must either be fixed in production or documented in ATLAS_V4_ADOPTION.md.",
      "",
      ...failures.map((failure) => `- ${failure}`),
    ].join("\n"),
  );
}

console.log(
  `Atlas v4 canonicalization check passed: ${comparedCount} token/theme pairs compared, ${acceptedDifferenceCount} intentional differences documented, required docs and Storybook references present.`,
);
