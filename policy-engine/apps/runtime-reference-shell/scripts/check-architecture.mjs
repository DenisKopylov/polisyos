import fs from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const allowedFiles = new Set([
  "README.md",
  "app.js",
  "eslint.config.mjs",
  "governedProjectionProof.js",
  "governedProjectionProof.test.mjs",
  "index.html",
  "package.json",
  "scripts/check-architecture.mjs",
  "styles.css",
  "tsconfig.json",
]);

const expectedImports = new Map([
  [
    "app.js",
    [
      "../../packages/runtime-api-client/canonicalRuntimeApiClient.js",
      "./governedProjectionProof.js",
    ],
  ],
  ["governedProjectionProof.js", []],
  [
    "governedProjectionProof.test.mjs",
    [
      "../../packages/runtime-api-client/canonicalRuntimeApiClient.js",
      "./governedProjectionProof.js",
      "node:assert/strict",
      "node:test",
    ],
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
      violations.push(
        `Unexpected file in runtime-reference-shell surface: ${file}`,
      );
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
    console.error("runtime-reference-shell architecture check failed:");
    for (const violation of violations) {
      console.error(`- ${violation}`);
    }
    process.exit(1);
  }

  console.log("runtime-reference-shell architecture checks passed.");
}

await main();
