import fs from "node:fs";

function formatBytes(value) {
  const kb = value / 1024;
  return `${kb.toFixed(1)} kB`;
}

function formatDelta(delta) {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${formatBytes(delta)}`;
}

function readStats(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function summarizeChunkDelta(baseList, headList) {
  const baseByName = new Map(baseList.map((item) => [item.name, item.bytes]));

  return headList.map((item) => ({
    delta: item.bytes - (baseByName.get(item.name) ?? 0),
    name: item.name,
    size: item.bytes,
  }));
}

const [basePath, headPath, outputPath] = process.argv.slice(2);

if (!basePath || !headPath) {
  throw new Error(
    "Usage: node compare-bundle-stats.mjs <base> <head> [output]",
  );
}

const base = readStats(basePath);
const head = readStats(headPath);

const lines = [
  "## Bundle Diff",
  "",
  "| Metric | Base | Head | Delta |",
  "| --- | ---: | ---: | ---: |",
  `| Initial JS | ${formatBytes(base.initialJsBytes)} | ${formatBytes(head.initialJsBytes)} | ${formatDelta(head.initialJsBytes - base.initialJsBytes)} |`,
  `| Initial CSS | ${formatBytes(base.initialCssBytes)} | ${formatBytes(head.initialCssBytes)} | ${formatDelta(head.initialCssBytes - base.initialCssBytes)} |`,
  "",
  "### Largest Route Chunks",
  "",
  "| Chunk | Head | Delta |",
  "| --- | ---: | ---: |",
  ...summarizeChunkDelta(base.largestRouteChunks, head.largestRouteChunks)
    .slice(0, 5)
    .map(
      (chunk) =>
        `| ${chunk.name} | ${formatBytes(chunk.size)} | ${formatDelta(chunk.delta)} |`,
    ),
  "",
  "### Vendor Chunks",
  "",
  "| Chunk | Head | Delta |",
  "| --- | ---: | ---: |",
  ...summarizeChunkDelta(base.vendorChunks, head.vendorChunks)
    .slice(0, 5)
    .map(
      (chunk) =>
        `| ${chunk.name} | ${formatBytes(chunk.size)} | ${formatDelta(chunk.delta)} |`,
    ),
  "",
];

const markdown = lines.join("\n");
if (outputPath) {
  fs.writeFileSync(outputPath, markdown, "utf8");
}
console.log(markdown);
