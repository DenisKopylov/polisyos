import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type RgbaColor = {
  a: number;
  b: number;
  g: number;
  r: number;
};

const TRANSPARENT: RgbaColor = { a: 0, b: 0, g: 0, r: 0 };
const WHITE: RgbaColor = { a: 1, b: 255, g: 255, r: 255 };

export function getPolicyEngineRoot() {
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
}

function readRuntimeFile(relativePath: string) {
  return fs.readFileSync(
    path.join(getPolicyEngineRoot(), relativePath),
    "utf8",
  );
}

export function readRuntimeStyles() {
  return readRuntimeFile("frontend/runtime-dashboard/src/styles.css");
}

function extractCssBlock(source: string, selector: string) {
  const selectorIndex = source.indexOf(selector);
  if (selectorIndex === -1) {
    return "";
  }

  const openBraceIndex = source.indexOf("{", selectorIndex);
  if (openBraceIndex === -1) {
    return "";
  }

  let depth = 0;
  for (let index = openBraceIndex; index < source.length; index += 1) {
    const character = source[index];
    if (character === "{") {
      depth += 1;
    }
    if (character === "}") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(openBraceIndex + 1, index);
      }
    }
  }

  return "";
}

function extractCssVariables(block: string) {
  const variables: Record<string, string> = {};
  const matches = block.matchAll(/(--[\w-]+)\s*:\s*([\s\S]*?);/g);

  for (const match of matches) {
    variables[match[1]] = match[2].replace(/\s+/g, " ").trim();
  }

  return variables;
}

export function loadThemeVariables(theme: "dark" | "light") {
  const styles = readRuntimeStyles();
  const lightThemeStyles = readRuntimeFile(
    "frontend/runtime-dashboard/src/styles/theme-light.css",
  );
  const darkThemeStyles = readRuntimeFile(
    "frontend/runtime-dashboard/src/styles/theme-dark.css",
  );

  const lightVariables = {
    ...extractCssVariables(extractCssBlock(styles, ":root {")),
    ...extractCssVariables(extractCssBlock(lightThemeStyles, ":root,")),
  };

  if (theme === "light") {
    return lightVariables;
  }

  return {
    ...lightVariables,
    ...extractCssVariables(
      extractCssBlock(darkThemeStyles, ':root[data-theme="dark"]'),
    ),
  };
}

export function resolveCssVariable(
  name: string,
  variables: Record<string, string>,
  seen = new Set<string>(),
): string {
  const rawValue = variables[name];
  if (!rawValue) {
    throw new Error(`Missing CSS variable: ${name}`);
  }

  const variableMatch = rawValue.match(/^var\((--[\w-]+)(?:,\s*([^)]+))?\)$/);
  if (!variableMatch) {
    return rawValue;
  }

  const nestedVariable = variableMatch[1];
  if (seen.has(nestedVariable)) {
    throw new Error(`Circular CSS variable reference detected for ${name}`);
  }

  if (variables[nestedVariable]) {
    const nextSeen = new Set(seen);
    nextSeen.add(nestedVariable);
    return resolveCssVariable(nestedVariable, variables, nextSeen);
  }

  if (variableMatch[2]) {
    return variableMatch[2].trim();
  }

  throw new Error(`Unresolved CSS variable ${nestedVariable} while reading ${name}`);
}

export function parseCssColor(input: string): RgbaColor {
  const normalized = input.replace(/\s+/g, " ").trim().toLowerCase();
  if (!normalized || normalized === "transparent") {
    return TRANSPARENT;
  }

  const hexMatch = normalized.match(/^#([\da-f]{3,8})$/i);
  if (hexMatch) {
    const hex = hexMatch[1];
    if (hex.length === 3 || hex.length === 4) {
      const expanded = hex
        .split("")
        .map((chunk) => chunk + chunk)
        .join("");
      return parseCssColor(`#${expanded}`);
    }

    if (hex.length === 6 || hex.length === 8) {
      return {
        a:
          hex.length === 8
            ? Number.parseInt(hex.slice(6, 8), 16) / 255
            : 1,
        b: Number.parseInt(hex.slice(4, 6), 16),
        g: Number.parseInt(hex.slice(2, 4), 16),
        r: Number.parseInt(hex.slice(0, 2), 16),
      };
    }
  }

  const rgbMatch = normalized.match(
    /^rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)$/,
  );
  if (rgbMatch) {
    return {
      a: rgbMatch[4] ? Number.parseFloat(rgbMatch[4]) : 1,
      b: Number.parseFloat(rgbMatch[3]),
      g: Number.parseFloat(rgbMatch[2]),
      r: Number.parseFloat(rgbMatch[1]),
    };
  }

  throw new Error(`Unsupported CSS color: ${input}`);
}

export function blendColors(
  foreground: RgbaColor,
  background: RgbaColor = WHITE,
): RgbaColor {
  const alpha = foreground.a + background.a * (1 - foreground.a);
  if (alpha <= 0) {
    return TRANSPARENT;
  }

  return {
    a: alpha,
    b:
      (foreground.b * foreground.a +
        background.b * background.a * (1 - foreground.a)) /
      alpha,
    g:
      (foreground.g * foreground.a +
        background.g * background.a * (1 - foreground.a)) /
      alpha,
    r:
      (foreground.r * foreground.a +
        background.r * background.a * (1 - foreground.a)) /
      alpha,
  };
}

function srgbToLinear(channel: number) {
  const normalized = channel / 255;
  if (normalized <= 0.04045) {
    return normalized / 12.92;
  }
  return ((normalized + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(color: RgbaColor) {
  return (
    srgbToLinear(color.r) * 0.2126 +
    srgbToLinear(color.g) * 0.7152 +
    srgbToLinear(color.b) * 0.0722
  );
}

export function contrastRatio(foreground: RgbaColor, background: RgbaColor) {
  const lighter = Math.max(
    relativeLuminance(foreground),
    relativeLuminance(background),
  );
  const darker = Math.min(
    relativeLuminance(foreground),
    relativeLuminance(background),
  );
  return (lighter + 0.05) / (darker + 0.05);
}

export function rgbaToHex(color: RgbaColor) {
  const solid = blendColors(color, WHITE);
  const toHex = (value: number) =>
    Math.round(value).toString(16).padStart(2, "0").toUpperCase();

  return `#${toHex(solid.r)}${toHex(solid.g)}${toHex(solid.b)}`;
}

export function readResolvedToken(
  variables: Record<string, string>,
  token: string,
) {
  return parseCssColor(resolveCssVariable(token, variables));
}

export function simulateColorBlindness(
  color: [number, number, number],
  matrix: readonly number[][],
): [number, number, number] {
  const [red, green, blue] = color;

  return [
    Math.round(red * matrix[0][0] + green * matrix[0][1] + blue * matrix[0][2]),
    Math.round(red * matrix[1][0] + green * matrix[1][1] + blue * matrix[1][2]),
    Math.round(red * matrix[2][0] + green * matrix[2][1] + blue * matrix[2][2]),
  ];
}

export function colorDistance(
  left: [number, number, number],
  right: [number, number, number],
) {
  return Math.hypot(left[0] - right[0], left[1] - right[1], left[2] - right[2]);
}

export function toRgbTuple(color: RgbaColor): [number, number, number] {
  const solid = blendColors(color, WHITE);
  return [solid.r, solid.g, solid.b];
}
