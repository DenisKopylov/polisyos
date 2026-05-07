import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const buildRoot = path.resolve(
  dashboardRoot,
  "../../_build/apps/runtime-dashboard",
);
const reportDir = path.join(buildRoot, "lighthouse-report");
const summaryPath = path.join(buildRoot, "lighthouse-summary.md");

fs.mkdirSync(buildRoot, { recursive: true });

function walk(directory) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const entries = fs.readdirSync(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const nextPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(nextPath));
      continue;
    }
    files.push(nextPath);
  }

  return files;
}

const reportFiles = walk(reportDir).filter((file) => file.endsWith(".json"));
const reports = reportFiles
  .map((file) => {
    try {
      return JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      return null;
    }
  })
  .filter(
    (report) =>
      report &&
      typeof report.finalDisplayedUrl === "string" &&
      typeof report.categories?.performance?.score === "number",
  );

const lines = [
  "## Lighthouse CI",
  "",
  "| Route | Performance |",
  "| --- | ---: |",
  ...reports.map(
    (report) =>
      `| ${report.finalDisplayedUrl} | ${Math.round(report.categories.performance.score * 100)} |`,
  ),
  "",
];

fs.writeFileSync(summaryPath, lines.join("\n"), "utf8");
console.log(lines.join("\n"));
