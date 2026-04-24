import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

const policyEngineRoot = getPolicyEngineRoot();
const dashboardRoot = path.join(policyEngineRoot, "frontend/runtime-dashboard");
const srcRoot = path.join(dashboardRoot, "src");

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

    files.push(fullPath);
  }

  return files;
}

function main() {
  const appProviders = fs.readFileSync(
    path.join(srcRoot, "app/providers/AppProviders.tsx"),
    "utf8",
  );
  const styles = fs.readFileSync(path.join(srcRoot, "styles.css"), "utf8");

  if (!appProviders.includes("ReducedMotionProvider")) {
    throw new Error("ReducedMotionProvider is not wired into AppProviders.");
  }

  if (!styles.includes("prefers-reduced-motion: reduce")) {
    throw new Error("styles.css is missing a prefers-reduced-motion override.");
  }

  const animatedFiles = walk(srcRoot).filter((filePath) =>
    filePath.endsWith(".ts") || filePath.endsWith(".tsx"),
  );

  const violations = animatedFiles.flatMap((filePath) => {
    const source = fs.readFileSync(filePath, "utf8");
    const usesMotion = source.includes('from "motion/react"');
    if (!usesMotion) {
      return [];
    }

    const usesImperativeAnimation = source.includes("animate(");
    const guardsReducedMotion =
      source.includes("useReducedMotion") ||
      source.includes("ReducedMotionProvider") ||
      source.includes("useReducedMotionPreference");

    if (usesImperativeAnimation && !guardsReducedMotion) {
      return [path.relative(policyEngineRoot, filePath)];
    }

    return [];
  });

  if (violations.length > 0) {
    throw new Error(
      [
        "Imperative motion calls without reduced-motion guards:",
        ...violations.map((violation) => `- ${violation}`),
      ].join("\n"),
    );
  }

  console.log("Reduced-motion checks passed.");
}

main();
