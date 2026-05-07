import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

const policyEngineRoot = getPolicyEngineRoot();
const WAVE2_COMPOSITION_SURFACES = [
  "apps/runtime-dashboard/src/app/layout",
  "apps/runtime-dashboard/src/features/artifacts/bureaucratic",
  "apps/runtime-dashboard/src/features/export/social",
  "apps/runtime-dashboard/src/features/runs/compare",
  "apps/runtime-dashboard/src/shared/charts",
  "apps/runtime-dashboard/src/shared/ui/counterfactual",
  "apps/runtime-dashboard/src/shared/ui/quantity",
  "apps/runtime-dashboard/src/shared/ui/trust-view",
  "apps/runtime-dashboard/src/styles",
];
const FORBIDDEN_PATTERNS: Array<{
  pattern: RegExp;
  reason: string;
}> = [
  { pattern: /\bblur-3xl\b/u, reason: "decorative blur blob" },
  { pattern: /\brounded-3xl\b/u, reason: "oversized rounded card token" },
  { pattern: /\btracking-\[-/u, reason: "negative letter spacing" },
  { pattern: /letter-spacing\s*:\s*-/u, reason: "negative letter spacing" },
  { pattern: /\borb\b|\bbokeh\b/iu, reason: "orb/bokeh decoration" },
];

function read(relativePath: string) {
  return fs.readFileSync(path.join(policyEngineRoot, relativePath), "utf8");
}

function assertNoRawSourceLeak(relativePath: string) {
  const source = read(relativePath);
  if (source.includes("rawSources")) {
    throw new Error(
      `${relativePath} must not render rawSources in share templates.`,
    );
  }
}

function walk(directory: string, files: string[] = []) {
  if (!fs.existsSync(directory)) {
    return files;
  }
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (/\.(css|ts|tsx)$/u.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}

function assertNoForbiddenCompositionTokens() {
  const files = WAVE2_COMPOSITION_SURFACES.flatMap((surface) =>
    walk(path.join(policyEngineRoot, surface)),
  );
  const failures: string[] = [];
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    for (const rule of FORBIDDEN_PATTERNS) {
      if (rule.pattern.test(source)) {
        failures.push(
          `${path.relative(policyEngineRoot, file)} contains ${rule.reason}`,
        );
      }
    }
    if (
      source.includes("ProvenancePopover") &&
      source.includes("TrustMetadata") &&
      !source.includes("data-trust-collapse=\"inspector\"") &&
      !source.includes("TrustInspector")
    ) {
      failures.push(
        `${path.relative(policyEngineRoot, file)} stacks provenance and trust without inspector collapse.`,
      );
    }
  }
  if (failures.length > 0) {
    throw new Error(`Composition rule violations:\n${failures.join("\n")}`);
  }
}

function main() {
  const compositionRules = read("docs/brand/COMPOSITION_RULES.md");
  if (!compositionRules.includes("Phase 2.7 Stacking Rules")) {
    throw new Error(
      "COMPOSITION_RULES.md is missing Phase 2.7 stacking rules.",
    );
  }

  for (const phrase of [
    "provenance",
    "counterfactual",
    "trust",
    "Anti-pattern",
  ]) {
    if (!compositionRules.toLowerCase().includes(phrase.toLowerCase())) {
      throw new Error(`COMPOSITION_RULES.md is missing ${phrase} guidance.`);
    }
  }

  assertNoRawSourceLeak(
    "apps/runtime-dashboard/src/features/export/social/OGCard.tsx",
  );
  assertNoRawSourceLeak(
    "apps/runtime-dashboard/src/features/export/social/EmailSummary.tsx",
  );
  assertNoRawSourceLeak(
    "apps/runtime-dashboard/src/features/export/social/generate-og.ts",
  );

  assertNoForbiddenCompositionTokens();

  console.log("Composition rule checks passed.");
}

main();
