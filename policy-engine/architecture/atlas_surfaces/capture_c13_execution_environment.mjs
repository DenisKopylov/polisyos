#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { arch, cpus, hostname, platform, release } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const policyEngineRoot = resolve(scriptDir, "../..");
const dashboardRoot = join(policyEngineRoot, "apps/runtime-dashboard");
const dashboardRequire = createRequire(join(dashboardRoot, "package.json"));

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`missing ${name}`);
  }
  return process.argv[index + 1];
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function packageTree(packageName) {
  const packageJson = dashboardRequire.resolve(`${packageName}/package.json`);
  const packageRoot = dirname(packageJson);
  const files = [];
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const absolute = join(directory, entry.name);
      if (entry.isDirectory()) {
        walk(absolute);
      } else if (entry.isFile()) {
        files.push(absolute);
      }
    }
  };
  walk(packageRoot);
  const rows = files
    .sort()
    .map((file) => {
      const bytes = readFileSync(file);
      return `${relative(packageRoot, file)}\0${bytes.length}\0${sha256(bytes)}\n`;
    })
    .join("");
  const metadata = JSON.parse(readFileSync(packageJson, "utf8"));
  return {
    file_count: files.length,
    tree_sha256: sha256(rows),
    version: metadata.version,
  };
}

const output = resolve(policyEngineRoot, argument("--output"));
const phase = argument("--phase");
if (!["before", "between", "after"].includes(phase)) {
  throw new Error(`invalid --phase: ${phase}`);
}

const { chromium } = dashboardRequire("@playwright/test");
const browser = await chromium.launch({ headless: true });
const browserVersion = browser.version();
await browser.close();

const fonts = Object.fromEntries(
  ["@fontsource/ibm-plex-mono", "@fontsource/manrope"].map((name) => [
    name,
    packageTree(name),
  ]),
);
const executionTuple = {
  architecture: `${arch()} ${cpus()[0]?.model ?? "unknown"}`,
  browser: `Chromium ${browserVersion}`,
  commit: execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: policyEngineRoot,
    encoding: "utf8",
  }).trim(),
  fonts,
  host: hostname(),
  kernel: `${platform()} ${release()}`,
  os: `macOS ${execFileSync("sw_vers", ["-productVersion"], {
    encoding: "utf8",
  }).trim()} (${execFileSync("sw_vers", ["-buildVersion"], {
    encoding: "utf8",
  }).trim()})`,
  playwright: dashboardRequire("@playwright/test/package.json").version,
};
const tupleBytes = canonicalJson(executionTuple);
const artifact = {
  measured_at: new Date().toISOString(),
  phase,
  schema_version: "1.0",
  tuple: executionTuple,
  tuple_sha256: sha256(tupleBytes),
};
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(artifact, null, 2)}\n`, { flag: "wx" });
if (statSync(output).size === 0) {
  throw new Error("environment receipt is empty");
}
process.stdout.write(`${output}\n${artifact.tuple_sha256}\n`);
