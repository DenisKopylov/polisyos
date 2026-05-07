import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

import {
  getPolicyEngineRoot,
  loadThemeVariables,
  type RgbaColor,
  readResolvedToken,
  rgbaToHex,
} from "./_a11yColor.ts";

type PairDefinition = {
  background: string;
  foreground: string;
  kind: "large" | "normal";
};

const LIGHT_BACKGROUNDS = ["--paper", "--canvas", "--sand"] as const;
const LIGHT_FOREGROUNDS = [
  "--ink",
  "--graphite",
  "--slate",
  "--teal",
  "--teal-vibrant",
  "--ember",
  "--gold",
] as const;
const DARK_BACKGROUNDS = ["--paper", "--canvas", "--surface"] as const;
const DARK_FOREGROUNDS = [
  "--ink",
  "--slate",
  "--teal",
  "--gold",
  "--ember",
] as const;
const REQUIRED_LIGHT_PAIRS: PairDefinition[] = [
  { background: "--paper", foreground: "--ink", kind: "normal" },
  { background: "--paper", foreground: "--graphite", kind: "normal" },
  { background: "--paper", foreground: "--slate", kind: "normal" },
  { background: "--paper", foreground: "--teal", kind: "normal" },
  { background: "--paper", foreground: "--ember", kind: "normal" },
  { background: "--paper", foreground: "--gold", kind: "normal" },
  { background: "--canvas", foreground: "--ink", kind: "normal" },
  { background: "--canvas", foreground: "--graphite", kind: "normal" },
  { background: "--canvas", foreground: "--slate", kind: "normal" },
  { background: "--sand", foreground: "--ink", kind: "normal" },
  { background: "--sand", foreground: "--graphite", kind: "normal" },
  { background: "--sand", foreground: "--slate", kind: "normal" },
  { background: "--paper", foreground: "--teal-vibrant", kind: "large" },
  { background: "--canvas", foreground: "--teal-vibrant", kind: "large" },
  { background: "--sand", foreground: "--teal-vibrant", kind: "large" },
];
const REQUIRED_DARK_PAIRS: PairDefinition[] = [
  { background: "--paper", foreground: "--ink", kind: "normal" },
  { background: "--paper", foreground: "--slate", kind: "normal" },
  { background: "--canvas", foreground: "--ink", kind: "normal" },
  { background: "--canvas", foreground: "--slate", kind: "normal" },
  { background: "--surface", foreground: "--ink", kind: "normal" },
  { background: "--surface", foreground: "--slate", kind: "normal" },
];

const SHOULD_WRITE = process.argv.includes("--write");
const policyEngineRoot = getPolicyEngineRoot();
const outputPath = path.join(policyEngineRoot, "docs/compliance/A11Y_CONTRAST.md");
const runtimeDashboardRequire = createRequire(
  path.join(policyEngineRoot, "apps/runtime-dashboard/package.json"),
);
const axeCore = runtimeDashboardRequire("axe-core") as {
  commons: {
    color: {
      Color: new (
        red: number,
        green: number,
        blue: number,
        alpha: number,
      ) => unknown;
      getContrast: (
        foreground: unknown,
        background: unknown,
      ) => number;
      hasValidContrastRatio: (
        background: unknown,
        foreground: unknown,
        fontSize: number,
        isBold: boolean,
      ) => {
        contrastRatio: number;
        expectedContrastRatio: number;
        isValid: boolean;
      };
    };
  };
};

function toAxeColor(color: RgbaColor) {
  return new axeCore.commons.color.Color(color.r, color.g, color.b, color.a);
}

function contrastRatio(foreground: RgbaColor, background: RgbaColor) {
  return axeCore.commons.color.getContrast(
    toAxeColor(foreground),
    toAxeColor(background),
  );
}

function classifyRatio(ratio: number) {
  if (ratio >= 4.5) {
    return "Pass";
  }
  if (ratio >= 3) {
    return "Large";
  }
  return "Fail";
}

function buildMatrix(
  theme: "dark" | "light",
  backgrounds: readonly string[],
  foregrounds: readonly string[],
) {
  const variables = loadThemeVariables(theme);

  return backgrounds.map((background) => {
    const backgroundColor = readResolvedToken(variables, background);

    return {
      background,
      backgroundHex: rgbaToHex(backgroundColor),
      cells: foregrounds.map((foreground) => {
        const foregroundColor = readResolvedToken(variables, foreground);
        const ratio = contrastRatio(foregroundColor, backgroundColor);
        return {
          foreground,
          ratio,
          status: classifyRatio(ratio),
        };
      }),
    };
  });
}

function formatMatrixTable(
  title: string,
  backgrounds: readonly string[],
  foregrounds: readonly string[],
  matrix: ReturnType<typeof buildMatrix>,
) {
  const header = [
    `## ${title}`,
    "",
    `| Background ↓ / Foreground → | ${foregrounds
      .map((foreground) => `\`${foreground}\``)
      .join(" | ")} |`,
    `| --- | ${foregrounds.map(() => "---").join(" | ")} |`,
  ];

  const rows = matrix.map((row) => {
    const cells = row.cells.map(
      (cell) => `${cell.ratio.toFixed(1)} ${cell.status}`,
    );
    return `| \`${row.background}\` ${row.backgroundHex} | ${cells.join(" | ")} |`;
  });

  return [...header, ...rows].join("\n");
}

function buildTokenTable(theme: "dark" | "light", tokens: readonly string[]) {
  const variables = loadThemeVariables(theme);
  const header = [
    "| Token | Hex |",
    "| --- | --- |",
  ];

  const rows = tokens.map((token) => {
    const color = readResolvedToken(variables, token);
    return `| \`${token}\` | \`${rgbaToHex(color)}\` |`;
  });

  return [...header, ...rows].join("\n");
}

function validatePair(
  variables: ReturnType<typeof loadThemeVariables>,
  pair: PairDefinition,
) {
  const background = readResolvedToken(variables, pair.background);
  const foreground = readResolvedToken(variables, pair.foreground);
  const validation = axeCore.commons.color.hasValidContrastRatio(
    toAxeColor(background),
    toAxeColor(foreground),
    pair.kind === "large" ? 24 : 16,
    false,
  );
  const ratio = validation.contrastRatio;
  const minimum = validation.expectedContrastRatio;

  if (validation.isValid) {
    return null;
  }

  return `${pair.background} / ${pair.foreground} resolved to ${ratio.toFixed(2)}:1 (needs ${minimum.toFixed(1)}:1)`;
}

function assertRequiredPairs() {
  const lightVariables = loadThemeVariables("light");
  const darkVariables = loadThemeVariables("dark");
  const failures = [
    ...REQUIRED_LIGHT_PAIRS.map((pair) => validatePair(lightVariables, pair)),
    ...REQUIRED_DARK_PAIRS.map((pair) => validatePair(darkVariables, pair)),
  ].flatMap((failure) => (failure ? [failure] : []));

  if (failures.length > 0) {
    throw new Error(
      `Contrast checks failed for required pairs:\n${failures.join("\n")}`,
    );
  }
}

function buildMarkdown() {
  const lightTokens = [
    "--paper",
    "--canvas",
    "--sand",
    "--ink",
    "--graphite",
    "--slate",
    "--teal",
    "--teal-vibrant",
    "--ember",
    "--gold",
  ] as const;
  const darkTokens = [
    "--paper",
    "--canvas",
    "--surface",
    "--ink",
    "--slate",
    "--teal",
    "--gold",
    "--ember",
  ] as const;
  const lightMatrix = buildMatrix(
    "light",
    LIGHT_BACKGROUNDS,
    LIGHT_FOREGROUNDS,
  );
  const darkMatrix = buildMatrix("dark", DARK_BACKGROUNDS, DARK_FOREGROUNDS);

  return [
    "# WCAG 2.2 AA Contrast Matrix",
    "",
    "> Auto-generated from `apps/runtime-dashboard/src/styles.css` by",
    "> `policy-engine/tools/design/check-contrast.ts` using `axe-core` color utilities.",
    "> Manual edits are not permitted.",
    "",
    `- Status: Generated`,
    `- Owner: Denis Kopylov`,
    `- Source: \`apps/runtime-dashboard/src/styles.css\``,
    `- Generator: \`policy-engine/tools/design/check-contrast.ts\``,
    "",
    "## Light Theme Tokens",
    "",
    buildTokenTable("light", lightTokens),
    "",
    formatMatrixTable(
      "Light Theme Matrix",
      LIGHT_BACKGROUNDS,
      LIGHT_FOREGROUNDS,
      lightMatrix,
    ),
    "",
    "## Dark Theme Tokens",
    "",
    buildTokenTable("dark", darkTokens),
    "",
    formatMatrixTable(
      "Dark Theme Matrix",
      DARK_BACKGROUNDS,
      DARK_FOREGROUNDS,
      darkMatrix,
    ),
    "",
    "## Enforcement",
    "",
    "- `Pass` means ratio >= 4.5:1 and is valid for normal text.",
    "- `Large` means ratio >= 3.0:1 and is valid only for large text or non-text contrast.",
    "- `Fail` means the pair is prohibited for body and small text unless a documented exemption exists.",
    "- Dark-theme raw brand accents (`--teal`, `--gold`, `--ember`) are observability-only matrix entries and are not text-safe foreground defaults.",
    "- PR gate: `node --experimental-strip-types ../../tools/design/check-contrast.ts`.",
    "",
  ].join("\n");
}

function main() {
  assertRequiredPairs();

  const markdown = buildMarkdown();
  if (SHOULD_WRITE) {
    fs.writeFileSync(outputPath, markdown, "utf8");
    console.log(`Wrote ${path.relative(policyEngineRoot, outputPath)}`);
    return;
  }

  if (!fs.existsSync(outputPath)) {
    throw new Error(`Missing generated contrast document: ${outputPath}`);
  }

  const current = fs.readFileSync(outputPath, "utf8");
  if (current !== markdown) {
    throw new Error(
      "A11Y_CONTRAST.md is out of date. Run `node --experimental-strip-types ../../tools/design/check-contrast.ts --write` from apps/runtime-dashboard.",
    );
  }

  console.log("Contrast checks passed.");
}

main();
