import fs from "node:fs";
import path from "node:path";

import { getPolicyEngineRoot } from "./_a11yColor.ts";

const REQUIRED_TOKENS = [
  "--motion-duration-instant",
  "--motion-duration-fast",
  "--motion-duration-moderate",
  "--motion-duration-slow",
  "--motion-ease-standard",
  "--motion-ease-enter",
  "--motion-ease-exit",
];

function read(relativePath: string) {
  return fs.readFileSync(
    path.join(getPolicyEngineRoot(), relativePath),
    "utf8",
  );
}

function main() {
  const motionCss = read("frontend/runtime-dashboard/src/styles/motion.css");
  const mediaCss = read("frontend/runtime-dashboard/src/styles/media.css");
  const motionDoc = read("docs/brand/MOTION.md");

  for (const token of REQUIRED_TOKENS) {
    if (!motionCss.includes(token)) {
      throw new Error(`Missing canonical motion token: ${token}`);
    }
  }

  if (!mediaCss.includes("prefers-reduced-motion: reduce")) {
    throw new Error("media.css must define the reduced-motion path.");
  }

  if (!motionDoc.includes("Forbidden Motion")) {
    throw new Error("MOTION.md must document forbidden motion.");
  }

  for (const surface of [
    "Temporal scrubber",
    "provenance popovers",
    "TrustInspector",
    "compare panels",
  ]) {
    if (!motionDoc.includes(surface)) {
      throw new Error(
        `MOTION.md is missing reduced-motion guidance for ${surface}.`,
      );
    }
  }

  if (!/transition-duration:\s*0\.?0?1ms/.test(mediaCss)) {
    throw new Error(
      "media.css must collapse transition duration under reduced motion.",
    );
  }

  const forbiddenPatterns = [/animation:\s*.*shimmer/i, /transition:\s*all\b/i];
  for (const pattern of forbiddenPatterns) {
    if (pattern.test(motionCss)) {
      throw new Error(`Forbidden motion pattern in motion.css: ${pattern}`);
    }
  }

  console.log("Motion token checks passed.");
}

main();
