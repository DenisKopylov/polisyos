import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

type QuantityClass = "decision" | "telemetry" | "layout" | "debug";

type Finding = {
  file: string;
  line: number;
  value: string;
  quantityClass: QuantityClass;
};

const args = process.argv.slice(2);
const verbose = args.includes("--verbose");
const roots = args.filter((arg) => arg !== "--verbose");
const policyEngineRoot = findPolicyEngineRoot();
const scanRoots = roots.length > 0 ? roots : ["frontend/runtime-dashboard/src"];
const require = createRequire(
  path.join(policyEngineRoot, "frontend/runtime-dashboard/package.json"),
);
const { classifyLine, lineHasClassificationComment } = require(
  "./eslint-plugin-local/rules/quantity-classifier.cjs",
);

const NUMBER_RE = /(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])/gu;

function findPolicyEngineRoot() {
  let cursor = process.cwd();
  while (cursor !== path.dirname(cursor)) {
    if (
      fs.existsSync(path.join(cursor, "pyproject.toml")) &&
      fs.existsSync(path.join(cursor, "frontend/runtime-dashboard"))
    ) {
      return cursor;
    }
    cursor = path.dirname(cursor);
  }
  throw new Error("Could not locate policy-engine root.");
}

function walk(directory: string, files: string[] = []) {
  const stats = fs.statSync(directory);
  if (stats.isFile()) {
    if (/\.(ts|tsx)$/u.test(directory)) {
      files.push(directory);
    }
    return files;
  }

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "dist") {
      continue;
    }
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (/\.(ts|tsx)$/u.test(fullPath)) {
      files.push(fullPath);
    }
  }
  return files;
}

function scanFile(filePath: string): Finding[] {
  const relative = path.relative(policyEngineRoot, filePath);
  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/u);
  return lines.flatMap((line, index) => {
    if (lineHasClassificationComment(line)) {
      return [];
    }
    const quantityClass = classifyLine(relative, line) as QuantityClass | null;
    if (quantityClass === null) {
      return [];
    }
    return Array.from(line.matchAll(NUMBER_RE))
      .filter((match) => !isInsideQuotedSegment(line, match.index ?? 0))
      .map((match) => ({
        file: relative,
        line: index + 1,
        value: match[0],
        quantityClass,
      }));
  });
}

function isInsideQuotedSegment(line: string, index: number) {
  let quote: string | null = null;
  let escaped = false;
  for (let i = 0; i < index; i += 1) {
    const char = line[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '"' || char === "'" || char === "`") {
      quote = char;
    }
  }
  return quote !== null;
}

function main() {
  const findings = scanRoots
    .flatMap((root) => walk(path.resolve(policyEngineRoot, root)))
    .flatMap(scanFile);
  const counts = findings.reduce<Record<QuantityClass, number>>(
    (acc, finding) => {
      acc[finding.quantityClass] += 1;
      return acc;
    },
    { decision: 0, telemetry: 0, layout: 0, debug: 0 },
  );

  console.log(
    JSON.stringify(
      {
        scannedRoots: scanRoots,
        total: findings.length,
        counts,
        findings: verbose
          ? findings
          : findings.filter((finding) => finding.quantityClass === "decision"),
      },
      null,
      2,
    ),
  );
  if (counts.decision > 0) {
    process.exitCode = 1;
  }
}

main();
