import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const packageSourceRoot = path.resolve(
  dashboardRoot,
  "../../packages/atlas-ui/src",
);
const dashboardSourceRoot = path.join(dashboardRoot, "src");
const assetsRoot = path.resolve(
  dashboardRoot,
  "../../_build/apps/runtime-dashboard/dist/assets",
);

const proofSignals = [
  {
    candidate: "h-[var(--control-height-sm)]",
    compiledFragment: "var(--control-height-sm)",
  },
  {
    candidate: "w-3/5",
    compiledFragment: ".w-3\\/5{",
  },
];

function sourceText(root) {
  return fs
    .readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.(?:ts|tsx)$/.test(entry.name))
    .map((entry) =>
      fs.readFileSync(path.join(entry.parentPath, entry.name), "utf8"),
    )
    .join("\n");
}

function countOccurrences(text, candidate) {
  return text.split(candidate).length - 1;
}

const packageSource = sourceText(packageSourceRoot);
const dashboardSource = sourceText(dashboardSourceRoot);
const compiledCss = fs
  .readdirSync(assetsRoot)
  .filter((name) => name.endsWith(".css"))
  .map((name) => fs.readFileSync(path.join(assetsRoot, name), "utf8"))
  .join("\n");
const failures = [];

for (const { candidate, compiledFragment } of proofSignals) {
  const packageOccurrences = countOccurrences(packageSource, candidate);
  const dashboardOccurrences = countOccurrences(dashboardSource, candidate);
  if (packageOccurrences === 0) {
    failures.push(`proof candidate missing from atlas-ui source: ${candidate}`);
    continue;
  }
  if (dashboardOccurrences !== 0) {
    failures.push(
      `proof candidate is no longer package-exclusive: ${candidate} (${dashboardOccurrences} dashboard occurrences)`,
    );
    continue;
  }
  if (!compiledCss.includes(compiledFragment)) {
    failures.push(
      `compiled CSS omitted atlas-ui candidate ${candidate} (expected ${compiledFragment})`,
    );
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(
    `atlas-ui Tailwind source: PASS (${proofSignals.length} package-exclusive candidates)`,
  );
}
