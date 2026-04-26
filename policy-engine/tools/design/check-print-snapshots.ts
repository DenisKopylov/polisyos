import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

const REQUIRED_PRINT_SELECTORS = [
  "@media print",
  ".monograph-page",
  ".bureaucratic-document",
  ".print-source-appendix",
  ".trust-metadata",
  '[data-print-hidden="true"]',
];
const REQUIRED_PRINT_SNAPSHOTS = [
  "decision-reading-view-a4-print-chromium-darwin.png",
  "run-detail-a4-print-chromium-darwin.png",
  "bureaucratic-document-a4-print-chromium-darwin.png",
  "policy-compare-a4-print-chromium-darwin.png",
  "scenario-a4-print-chromium-darwin.png",
];
const REQUIRED_VISUAL_CONTRACTS = [
  "decision packet reading view A4 print",
  "run detail A4 print",
  "bureaucratic document A4 print",
  "policy compare A4 print",
  "counterfactual scenario A4 print",
  'emulateMedia({ media: "print" })',
  ...REQUIRED_PRINT_SNAPSHOTS.map((name) =>
    name.replace("-chromium-darwin", ""),
  ),
];

function read(relativePath: string) {
  return fs.readFileSync(
    path.join(getPolicyEngineRoot(), relativePath),
    "utf8",
  );
}

function main() {
  const printCss = read("frontend/runtime-dashboard/src/styles/print.css");
  const exportDoc = read("docs/brand/PRINT_AND_EXPORT.md");
  const visualSpec = read(
    "frontend/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts",
  );

  for (const selector of REQUIRED_PRINT_SELECTORS) {
    if (!printCss.includes(selector)) {
      throw new Error(`print.css is missing print contract hook: ${selector}`);
    }
  }

  for (const fixture of [
    "Run Detail",
    "Reading View",
    "bureaucratic document",
    "provenance summary",
    "source appendix",
  ]) {
    if (!exportDoc.toLowerCase().includes(fixture.toLowerCase())) {
      throw new Error(
        `PRINT_AND_EXPORT.md is missing fixture/snapshot guidance: ${fixture}`,
      );
    }
  }

  for (const contract of REQUIRED_VISUAL_CONTRACTS) {
    if (!visualSpec.includes(contract)) {
      throw new Error(
        `runtime-dashboard.visual.spec.ts is missing print snapshot contract: ${contract}`,
      );
    }
  }

  for (const snapshot of REQUIRED_PRINT_SNAPSHOTS) {
    const snapshotPath = path.join(
      getPolicyEngineRoot(),
      "frontend/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots",
      snapshot,
    );
    const snapshotStat = fs.statSync(snapshotPath);
    if (snapshotStat.size < 80_000) {
      throw new Error(
        `Print snapshot looks too small to cover an A4 decision packet: ${snapshot}`,
      );
    }
  }

  for (const filePath of [
    "frontend/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx",
    "frontend/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticArtifactView.tsx",
    "frontend/runtime-dashboard/src/features/artifacts/bureaucratic/export/parity-check.test.ts",
  ]) {
    const source = read(filePath);
    if (
      !source.includes("print") &&
      !source.includes("Print") &&
      !source.includes("export")
    ) {
      throw new Error(
        `${filePath} is no longer covered by the print/export contract.`,
      );
    }
  }

  console.log("Print snapshot checks passed.");
}

main();
