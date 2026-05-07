import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const buildRoot = path.resolve(
  dashboardRoot,
  "../../_build/apps/runtime-dashboard",
);
const testResultsDir = path.join(buildRoot, "test-results");
const summaryPath = path.join(buildRoot, "visual-regression-summary.md");

fs.mkdirSync(buildRoot, { recursive: true });

function listDiffArtifacts(directory) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const entries = fs.readdirSync(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const nextPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...listDiffArtifacts(nextPath));
      continue;
    }
    if (entry.name.includes("-diff")) {
      files.push(path.relative(buildRoot, nextPath));
    }
  }

  return files;
}

const diffArtifacts = listDiffArtifacts(testResultsDir);
const lines = [
  "## Visual Regression",
  "",
  diffArtifacts.length === 0
    ? "No visual diff artifacts were generated."
    : `Generated diff artifacts: ${diffArtifacts.length}`,
  "",
  ...diffArtifacts.map((artifact) => `- ${artifact}`),
  "",
];

fs.writeFileSync(summaryPath, lines.join("\n"), "utf8");
console.log(lines.join("\n"));
