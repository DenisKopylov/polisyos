import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(scriptDir, "..");
const distDir = path.resolve(
  dashboardRoot,
  "../../_build/frontend/runtime-dashboard/dist",
);
const manifestPath = path.join(distDir, ".vite", "manifest.json");
const outputPath = process.argv[2] || path.join(distDir, "bundle-stats.json");

if (!fs.existsSync(manifestPath)) {
  throw new Error(`Missing Vite manifest at ${manifestPath}`);
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

function fileBytes(file) {
  const absolutePath = path.join(distDir, file);
  if (!fs.existsSync(absolutePath)) {
    return 0;
  }
  return fs.statSync(absolutePath).size;
}

function collectImportedFiles(file, seen = new Set()) {
  if (!file || seen.has(file)) {
    return seen;
  }

  seen.add(file);
  for (const entry of Object.values(manifest)) {
    if (entry.file !== file) {
      continue;
    }
    for (const importedFile of entry.imports ?? []) {
      const importedEntry = Object.values(manifest).find(
        (candidate) => candidate.file === importedFile,
      );
      if (importedEntry?.file) {
        collectImportedFiles(importedEntry.file, seen);
      }
    }
  }

  return seen;
}

const assets = Object.entries(manifest)
  .filter(([, entry]) => typeof entry.file === "string")
  .map(([key, entry]) => ({
    bytes: fileBytes(entry.file),
    dynamicImports: entry.dynamicImports ?? [],
    file: entry.file,
    imports: entry.imports ?? [],
    isEntry: Boolean(entry.isEntry),
    key,
    name: entry.name ?? key,
  }));

const mainEntry =
  manifest["src/main.tsx"] ??
  manifest["index.html"] ??
  Object.values(manifest).find((entry) => entry.isEntry);
const initialFiles = Array.from(
  mainEntry?.file ? collectImportedFiles(mainEntry.file) : [],
);
const initialJsBytes = initialFiles
  .filter((file) => file.endsWith(".js"))
  .reduce((total, file) => total + fileBytes(file), 0);
const initialCssBytes = initialFiles
  .filter((file) => file.endsWith(".css"))
  .reduce((total, file) => total + fileBytes(file), 0);

const vendorChunks = assets
  .filter(
    (asset) => asset.file.endsWith(".js") && asset.file.includes("vendor"),
  )
  .sort((left, right) => right.bytes - left.bytes)
  .slice(0, 10);

const largestRouteChunks = assets
  .filter(
    (asset) => asset.file.endsWith(".js") && !asset.file.includes("vendor"),
  )
  .sort((left, right) => right.bytes - left.bytes)
  .slice(0, 10);

const stats = {
  assets,
  generatedAt: new Date().toISOString(),
  initialCssBytes,
  initialJsBytes,
  largestRouteChunks,
  vendorChunks,
};

fs.writeFileSync(outputPath, JSON.stringify(stats, null, 2), "utf8");
console.log(outputPath);
