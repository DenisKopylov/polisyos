import fs from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const allowedFiles = new Set([
  ".prettierignore",
  "README.md",
  "eslint.config.mjs",
  "package-lock.json",
  "package.json",
  "runtimeApiClient.js",
  "runtimeApiClient.test.mjs",
  "runtimeApiClient.ts",
  "scripts/check-architecture.mjs",
  "tsconfig.json",
]);

const expectedImports = new Map([
  ["runtimeApiClient.ts", []],
  ["runtimeApiClient.js", []],
  [
    "runtimeApiClient.test.mjs",
    ["./runtimeApiClient.js", "node:assert/strict", "node:test"],
  ],
  ["scripts/check-architecture.mjs", ["node:fs/promises", "node:path"]],
]);

const importPattern =
  /\bimport\s+(?:[^"'()]+\s+from\s+)?["']([^"']+)["']|\bimport\(\s*["']([^"']+)["']\s*\)/g;

async function listFiles(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      if (entry.name === "node_modules") {
        return [];
      }
      const resolved = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        return listFiles(resolved);
      }
      return [resolved];
    }),
  );

  return files.flat();
}

function toRelative(filePath) {
  return path.relative(projectRoot, filePath).replaceAll(path.sep, "/");
}

async function readImports(relativePath) {
  const source = await fs.readFile(
    path.join(projectRoot, relativePath),
    "utf8",
  );
  const imports = [];
  let match;
  while ((match = importPattern.exec(source)) !== null) {
    imports.push(match[1] ?? match[2]);
  }
  return imports.sort();
}

async function main() {
  const files = (await listFiles(projectRoot)).map(toRelative).sort();
  const violations = [];

  for (const file of files) {
    if (!allowedFiles.has(file)) {
      violations.push(`Unexpected file in runtime-api-client surface: ${file}`);
    }
  }

  for (const [file, expected] of expectedImports) {
    const imports = await readImports(file);
    if (JSON.stringify(imports) !== JSON.stringify(expected)) {
      violations.push(
        `${file} has unexpected imports: expected ${JSON.stringify(expected)}, received ${JSON.stringify(imports)}`,
      );
    }
  }

  if (violations.length > 0) {
    console.error("runtime-api-client architecture check failed:");
    for (const violation of violations) {
      console.error(`- ${violation}`);
    }
    process.exit(1);
  }

  console.log("runtime-api-client architecture checks passed.");
}

await main();
