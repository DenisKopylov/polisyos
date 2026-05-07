import fs from "node:fs";
import path from "node:path";

const SHOULD_WRITE = process.argv.includes("--write");
const args = process.argv.slice(2).filter((arg) => arg !== "--write");
const roots = args.length > 0 ? args : ["apps/runtime-dashboard/src"];
const policyEngineRoot = findPolicyEngineRoot();
const JSX_NUMBER_RE = />\s*\{(-?\d+(?:\.\d+)?)\}\s*</gu;
const QUANTITY_IMPORT = 'import { Quantity } from "@/shared/ui/quantity";';

type Candidate = {
  file: string;
  count: number;
};

function findPolicyEngineRoot() {
  let cursor = process.cwd();
  while (cursor !== path.dirname(cursor)) {
    if (
      fs.existsSync(path.join(cursor, "pyproject.toml")) &&
      fs.existsSync(path.join(cursor, "apps/runtime-dashboard"))
    ) {
      return cursor;
    }
    cursor = path.dirname(cursor);
  }
  throw new Error("Could not locate policy-engine root.");
}

function walk(directory: string, files: string[] = []) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "dist") {
      continue;
    }
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (fullPath.endsWith(".tsx")) {
      files.push(fullPath);
    }
  }
  return files;
}

function quantityEnvelope(point: string) {
  return `<Quantity value={{ point: ${point}, unit: { code: "1", system: "ucum", display: "value" }, metric_id: "codemod_migrated_number", lineage: { id: "untraced", status: "untraced", freshness: "unknown", reason_code: "codemod_pending_lineage", tracking_issue: "POLICYOS-QUANTITY-TODO" }, quantity_class: "decision" }} />`;
}

function addQuantityImport(source: string) {
  if (source.includes("@/shared/ui/quantity")) {
    return source;
  }
  const importMatches = Array.from(source.matchAll(/^import .+;$/gmu));
  const lastImport = importMatches.at(-1);
  if (!lastImport || lastImport.index === undefined) {
    return `${QUANTITY_IMPORT}\n\n${source}`;
  }
  const insertAt = lastImport.index + lastImport[0].length;
  return `${source.slice(0, insertAt)}\n${QUANTITY_IMPORT}${source.slice(insertAt)}`;
}

function processFile(filePath: string): Candidate | null {
  const source = fs.readFileSync(filePath, "utf8");
  let count = 0;
  const migrated = source.replace(JSX_NUMBER_RE, (_match, point: string) => {
    count += 1;
    return `>${quantityEnvelope(point)}<`;
  });

  if (count === 0) {
    return null;
  }

  if (SHOULD_WRITE) {
    fs.writeFileSync(filePath, addQuantityImport(migrated), "utf8");
  }

  return {
    file: path.relative(policyEngineRoot, filePath),
    count,
  };
}

function main() {
  const candidates = roots
    .flatMap((root) => walk(path.resolve(policyEngineRoot, root)))
    .flatMap((filePath) => {
      const candidate = processFile(filePath);
      return candidate ? [candidate] : [];
    });

  console.log(
    JSON.stringify(
      {
        write: SHOULD_WRITE,
        files: candidates.length,
        replacements: candidates.reduce((sum, item) => sum + item.count, 0),
        candidates,
      },
      null,
      2,
    ),
  );
}

main();
