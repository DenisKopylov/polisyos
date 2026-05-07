import fs from "node:fs/promises";
import path from "node:path";
import zlib from "node:zlib";

const projectRoot = process.cwd();
const distDir = path.resolve(
  projectRoot,
  "../../_build/apps/runtime-dashboard/dist",
);
const manifestPath = path.join(distDir, ".vite", "manifest.json");

const budgets = {
  initialJsRawMaxBytes: 780_000,
  initialJsGzipMaxBytes: 250_000,
  largestAppChunkRawMaxBytes: 190_000,
  largestAppChunkGzipMaxBytes: 55_000,
  vendorRawMaxBytes: 300_000,
  vendorGzipMaxBytes: 95_000,
  vendorReactRawMaxBytes: 195_000,
  vendorReactGzipMaxBytes: 60_000,
  vendorRechartsRawMaxBytes: 285_000,
  vendorRechartsGzipMaxBytes: 65_000,
};

function formatKilobytes(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`;
}

async function readManifest() {
  const manifestRaw = await fs.readFile(manifestPath, "utf8");
  return JSON.parse(manifestRaw);
}

async function fileSize(relativeFile) {
  const stats = await fs.stat(path.join(distDir, relativeFile));
  return stats.size;
}

async function gzipSize(relativeFile) {
  const content = await fs.readFile(path.join(distDir, relativeFile));
  return zlib.gzipSync(content).length;
}

async function collectInitialAssets(manifest) {
  const entry = Object.entries(manifest).find(([, chunk]) => chunk.isEntry);
  if (!entry) {
    throw new Error("Unable to find the Vite entry chunk in manifest.json");
  }

  const [entryKey] = entry;
  const visited = new Set();
  const queue = [entryKey];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    const currentChunk = manifest[current];
    if (!currentChunk || visited.has(currentChunk.file)) {
      continue;
    }
    visited.add(currentChunk.file);
    queue.push(...(currentChunk.imports ?? []));
  }

  return [...visited];
}

async function main() {
  const manifest = await readManifest();
  const initialAssets = await collectInitialAssets(manifest);
  const initialJsAssets = initialAssets.filter((asset) =>
    asset.endsWith(".js"),
  );
  const initialRawSizes = await Promise.all(
    initialJsAssets.map((asset) => fileSize(asset)),
  );
  const initialGzipSizes = await Promise.all(
    initialJsAssets.map((asset) => gzipSize(asset)),
  );
  const initialJsRawBytes = initialRawSizes.reduce(
    (sum, size) => sum + size,
    0,
  );
  const initialJsGzipBytes = initialGzipSizes.reduce(
    (sum, size) => sum + size,
    0,
  );

  const chunks = Object.values(manifest);
  const matchChunk = (prefix) =>
    chunks.find((chunk) => chunk.file.includes(`assets/${prefix}-`));
  const vendorChunk = matchChunk("vendor");
  const vendorReactChunk = matchChunk("vendor-react");
  const vendorRechartsChunk = matchChunk("vendor-recharts");

  const vendorRawBytes = vendorChunk ? await fileSize(vendorChunk.file) : 0;
  const vendorGzipBytes = vendorChunk ? await gzipSize(vendorChunk.file) : 0;
  const vendorReactRawBytes = vendorReactChunk
    ? await fileSize(vendorReactChunk.file)
    : 0;
  const vendorReactGzipBytes = vendorReactChunk
    ? await gzipSize(vendorReactChunk.file)
    : 0;
  const vendorRechartsRawBytes = vendorRechartsChunk
    ? await fileSize(vendorRechartsChunk.file)
    : 0;
  const vendorRechartsGzipBytes = vendorRechartsChunk
    ? await gzipSize(vendorRechartsChunk.file)
    : 0;

  const initialAppChunks = initialJsAssets.filter(
    (asset) => !asset.includes("/vendor-"),
  );
  const appChunkMetrics = await Promise.all(
    initialAppChunks.map(async (asset) => ({
      file: asset,
      gzip: await gzipSize(asset),
      raw: await fileSize(asset),
    })),
  );
  const largestAppChunk =
    appChunkMetrics.sort((left, right) => right.raw - left.raw)[0] ?? null;

  const violations = [];
  if (initialJsRawBytes > budgets.initialJsRawMaxBytes) {
    violations.push(
      `Initial JS raw budget exceeded: ${formatKilobytes(initialJsRawBytes)} > ${formatKilobytes(budgets.initialJsRawMaxBytes)}`,
    );
  }
  if (initialJsGzipBytes > budgets.initialJsGzipMaxBytes) {
    violations.push(
      `Initial JS gzip budget exceeded: ${formatKilobytes(initialJsGzipBytes)} > ${formatKilobytes(budgets.initialJsGzipMaxBytes)}`,
    );
  }
  if (
    largestAppChunk &&
    largestAppChunk.raw > budgets.largestAppChunkRawMaxBytes
  ) {
    violations.push(
      `Largest app chunk raw budget exceeded (${largestAppChunk.file}): ${formatKilobytes(largestAppChunk.raw)} > ${formatKilobytes(budgets.largestAppChunkRawMaxBytes)}`,
    );
  }
  if (
    largestAppChunk &&
    largestAppChunk.gzip > budgets.largestAppChunkGzipMaxBytes
  ) {
    violations.push(
      `Largest app chunk gzip budget exceeded (${largestAppChunk.file}): ${formatKilobytes(largestAppChunk.gzip)} > ${formatKilobytes(budgets.largestAppChunkGzipMaxBytes)}`,
    );
  }
  if (vendorRawBytes > budgets.vendorRawMaxBytes) {
    violations.push(
      `Vendor chunk raw budget exceeded: ${formatKilobytes(vendorRawBytes)} > ${formatKilobytes(budgets.vendorRawMaxBytes)}`,
    );
  }
  if (vendorGzipBytes > budgets.vendorGzipMaxBytes) {
    violations.push(
      `Vendor chunk gzip budget exceeded: ${formatKilobytes(vendorGzipBytes)} > ${formatKilobytes(budgets.vendorGzipMaxBytes)}`,
    );
  }
  if (vendorReactRawBytes > budgets.vendorReactRawMaxBytes) {
    violations.push(
      `vendor-react raw budget exceeded: ${formatKilobytes(vendorReactRawBytes)} > ${formatKilobytes(budgets.vendorReactRawMaxBytes)}`,
    );
  }
  if (vendorReactGzipBytes > budgets.vendorReactGzipMaxBytes) {
    violations.push(
      `vendor-react gzip budget exceeded: ${formatKilobytes(vendorReactGzipBytes)} > ${formatKilobytes(budgets.vendorReactGzipMaxBytes)}`,
    );
  }
  if (vendorRechartsRawBytes > budgets.vendorRechartsRawMaxBytes) {
    violations.push(
      `vendor-recharts raw budget exceeded: ${formatKilobytes(vendorRechartsRawBytes)} > ${formatKilobytes(budgets.vendorRechartsRawMaxBytes)}`,
    );
  }
  if (vendorRechartsGzipBytes > budgets.vendorRechartsGzipMaxBytes) {
    violations.push(
      `vendor-recharts gzip budget exceeded: ${formatKilobytes(vendorRechartsGzipBytes)} > ${formatKilobytes(budgets.vendorRechartsGzipMaxBytes)}`,
    );
  }

  console.log("Bundle budget summary");
  console.log(
    `- initial JS: ${formatKilobytes(initialJsRawBytes)} raw / ${formatKilobytes(initialJsGzipBytes)} gzip`,
  );
  console.log(
    `- vendor: ${formatKilobytes(vendorRawBytes)} raw / ${formatKilobytes(vendorGzipBytes)} gzip`,
  );
  console.log(
    `- vendor-react: ${formatKilobytes(vendorReactRawBytes)} raw / ${formatKilobytes(vendorReactGzipBytes)} gzip`,
  );
  console.log(
    `- vendor-recharts: ${formatKilobytes(vendorRechartsRawBytes)} raw / ${formatKilobytes(vendorRechartsGzipBytes)} gzip`,
  );
  if (largestAppChunk) {
    console.log(
      `- largest app chunk (${largestAppChunk.file}): ${formatKilobytes(largestAppChunk.raw)} raw / ${formatKilobytes(largestAppChunk.gzip)} gzip`,
    );
  }

  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(violation);
    }
    process.exitCode = 1;
  }
}

await main();
