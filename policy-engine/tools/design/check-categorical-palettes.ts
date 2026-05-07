import {
  categorical12,
  categorical8,
} from "../../apps/runtime-dashboard/src/shared/charts/categorical-palettes.ts";

const REQUIRED_PATTERNS = new Set([
  "solid",
  "diagonal",
  "cross",
  "dot",
  "dash",
  "ring",
]);
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

function hexToRgb(hex: string) {
  const match = hex.match(/^#([\da-f]{6})$/i);
  if (!match) {
    throw new Error(`Palette color must be six-digit hex: ${hex}`);
  }

  return {
    b: Number.parseInt(match[1].slice(4, 6), 16),
    g: Number.parseInt(match[1].slice(2, 4), 16),
    r: Number.parseInt(match[1].slice(0, 2), 16),
  };
}

function hueBucket(hex: string) {
  const { b, g, r } = hexToRgb(hex);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  if (delta === 0) {
    return "neutral";
  }

  let hue = 0;
  if (max === r) {
    hue = ((g - b) / delta) % 6;
  } else if (max === g) {
    hue = (b - r) / delta + 2;
  } else {
    hue = (r - g) / delta + 4;
  }

  return Math.round(((hue * 60 + 360) % 360) / 45);
}

function colorDistance(leftHex: string, rightHex: string) {
  const left = hexToRgb(leftHex);
  const right = hexToRgb(rightHex);
  return Math.hypot(left.r - right.r, left.g - right.g, left.b - right.b);
}

function simulateColorBlindness(
  hex: string,
  matrix: readonly (readonly number[])[],
) {
  const { b, g, r } = hexToRgb(hex);
  return {
    b: r * matrix[2][0] + g * matrix[2][1] + b * matrix[2][2],
    g: r * matrix[1][0] + g * matrix[1][1] + b * matrix[1][2],
    r: r * matrix[0][0] + g * matrix[0][1] + b * matrix[0][2],
  };
}

function rgbDistance(
  left: ReturnType<typeof simulateColorBlindness>,
  right: ReturnType<typeof simulateColorBlindness>,
) {
  return Math.hypot(left.r - right.r, left.g - right.g, left.b - right.b);
}

function assertPalette(
  name: string,
  palette: typeof categorical12,
  size: number,
) {
  if (palette.length !== size) {
    throw new Error(`${name} must contain exactly ${size} colors.`);
  }

  const names = new Set(palette.map((swatch) => swatch.name));
  if (names.size !== palette.length) {
    throw new Error(`${name} contains duplicate semantic names.`);
  }

  const patterns = new Set(palette.map((swatch) => swatch.pattern));
  const shapes = new Set(palette.map((swatch) => swatch.shape));
  for (const pattern of REQUIRED_PATTERNS) {
    if (!patterns.has(pattern as never)) {
      throw new Error(
        `${name} is missing non-color pattern fallback: ${pattern}`,
      );
    }
  }
  if (shapes.size < 6) {
    throw new Error(`${name} must include shape fallbacks for dense charts.`);
  }

  const hueBuckets = new Set(palette.map((swatch) => hueBucket(swatch.color)));
  if (hueBuckets.size < 6) {
    throw new Error(`${name} collapses into too few hue families.`);
  }

  for (let index = 0; index < palette.length; index += 1) {
    for (
      let nextIndex = index + 1;
      nextIndex < palette.length;
      nextIndex += 1
    ) {
      const left = palette[index];
      const right = palette[nextIndex];
      const distance = colorDistance(left.color, right.color);
      if (distance < 38) {
        throw new Error(
          `${name} colors ${left.name}/${right.name} are too similar (${distance.toFixed(1)}).`,
        );
      }

      for (const [simulationName, matrix] of Object.entries(
        COLOR_BLIND_MATRICES,
      )) {
        const simulatedDistance = rgbDistance(
          simulateColorBlindness(left.color, matrix),
          simulateColorBlindness(right.color, matrix),
        );
        if (simulatedDistance < 18 && left.pattern === right.pattern) {
          throw new Error(
            `${name} colors ${left.name}/${right.name} collapse under ${simulationName} and share pattern ${left.pattern}.`,
          );
        }
      }
    }
  }

  for (const swatch of palette) {
    if (!swatch.highContrastColor) {
      throw new Error(
        `${name} swatch ${swatch.name} is missing high-contrast fallback.`,
      );
    }
  }
}

function main() {
  assertPalette("Categorical-8", categorical8, 8);
  assertPalette("Categorical-12", categorical12, 12);
  console.log("Categorical palette checks passed.");
}

main();
