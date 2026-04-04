import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dashboardRoot = path.dirname(
  fileURLToPath(new URL("../package.json", import.meta.url)),
);
const summaryPath = path.resolve(
  dashboardRoot,
  "coverage/coverage-summary.json",
);
const baselinePath = path.resolve(dashboardRoot, "coverage-baseline.json");
const tolerance = Number.parseFloat(
  process.env.COVERAGE_RATCHET_TOLERANCE ?? "0",
);
const metrics = ["lines", "statements", "functions", "branches"];
const absoluteMinimums = {
  branches: 70,
  functions: 80,
  lines: 85,
  statements: 85,
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

if (!fs.existsSync(summaryPath)) {
  console.error(`Coverage summary not found: ${summaryPath}`);
  process.exit(1);
}

if (!fs.existsSync(baselinePath)) {
  console.error(`Coverage baseline not found: ${baselinePath}`);
  process.exit(1);
}

const summary = readJson(summaryPath);
const baseline = readJson(baselinePath);
const failures = [];

console.log("Coverage ratchet summary");

for (const metric of metrics) {
  const actual = summary.total?.[metric]?.pct;
  const ratchetMinimum = baseline.global?.[metric];
  const absoluteMinimum = absoluteMinimums[metric];

  if (
    typeof actual !== "number" ||
    typeof ratchetMinimum !== "number" ||
    typeof absoluteMinimum !== "number"
  ) {
    failures.push(`Missing ${metric} coverage data`);
    continue;
  }

  const enforcedMinimum = Math.max(ratchetMinimum, absoluteMinimum);

  console.log(
    `- ${metric}: ${actual.toFixed(2)}% actual / ${ratchetMinimum.toFixed(2)}% baseline / ${absoluteMinimum.toFixed(2)}% target / ${enforcedMinimum.toFixed(2)}% enforced`,
  );

  if (actual + tolerance < enforcedMinimum) {
    failures.push(
      `${metric} coverage below enforced minimum: ${actual.toFixed(2)}% < ${enforcedMinimum.toFixed(2)}%`,
    );
  }
}

if (failures.length > 0) {
  console.error("\nCoverage ratchet failed");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}
