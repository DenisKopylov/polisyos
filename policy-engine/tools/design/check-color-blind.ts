import fs from "node:fs";
import path from "node:path";

import {
  colorDistance,
  getPolicyEngineRoot,
  loadThemeVariables,
  readResolvedToken,
  simulateColorBlindness,
  toRgbTuple,
} from "./_a11yColor.ts";

const COLOR_BLIND_MATRICES = {
  deuteranope: [
    [0.625, 0.375, 0],
    [0.7, 0.3, 0],
    [0, 0.3, 0.7],
  ],
  protanope: [
    [0.56667, 0.43333, 0],
    [0.55833, 0.44167, 0],
    [0, 0.24167, 0.75833],
  ],
  tritanope: [
    [0.95, 0.05, 0],
    [0, 0.43333, 0.56667],
    [0, 0.475, 0.525],
  ],
} as const;

const policyEngineRoot = getPolicyEngineRoot();

function main() {
  const variables = loadThemeVariables("light");
  const pairs = [
    {
      left: { color: toRgbTuple(readResolvedToken(variables, "--gold")), label: "--gold" },
      minimumDistance: 15,
      right: { color: toRgbTuple(readResolvedToken(variables, "--ember")), label: "--ember" },
    },
    {
      left: { color: toRgbTuple(readResolvedToken(variables, "--teal")), label: "--teal" },
      minimumDistance: 20,
      right: { color: toRgbTuple(readResolvedToken(variables, "--slate")), label: "--slate" },
    },
  ];

  const patternSource = fs.readFileSync(
    path.join(
      policyEngineRoot,
      "frontend/runtime-dashboard/src/shared/charts/patterns/UncertaintyPatterns.tsx",
    ),
    "utf8",
  );

  for (const requiredPattern of ["assumed", "disputed", "estimated"]) {
    if (!patternSource.includes(requiredPattern)) {
      throw new Error(`Missing uncertainty pattern definition: ${requiredPattern}`);
    }
  }

  const failures = Object.entries(COLOR_BLIND_MATRICES).flatMap(
    ([simulationName, matrix]) =>
      pairs.flatMap((pair) => {
        const distance = colorDistance(
          simulateColorBlindness(pair.left.color, matrix),
          simulateColorBlindness(pair.right.color, matrix),
        );

        if (distance >= pair.minimumDistance) {
          return [];
        }

        return [
          `${simulationName}: ${pair.left.label} vs ${pair.right.label} collapsed to ${distance.toFixed(2)} (needs ${pair.minimumDistance})`,
        ];
      }),
  );

  if (failures.length > 0) {
    throw new Error(["Color-blind checks failed:", ...failures].join("\n"));
  }

  console.log("Color-blind checks passed.");
}

main();
