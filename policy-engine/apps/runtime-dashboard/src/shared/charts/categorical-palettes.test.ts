import { describe, expect, it } from "vitest";

import {
  categorical12,
  categorical8,
  categoricalCssVars,
  categoricalSwatch,
} from "./categorical-palettes";

describe("categorical palettes", () => {
  it("ships 8 and 12 named swatches with non-color fallbacks", () => {
    expect(categorical8).toHaveLength(8);
    expect(categorical12).toHaveLength(12);
    expect(new Set(categorical12.map((swatch) => swatch.name)).size).toBe(12);
    expect(
      categorical12.every((swatch) => swatch.pattern && swatch.shape),
    ).toBe(true);
  });

  it("does not collapse into one hue family", () => {
    const hueBuckets = new Set(
      categorical12.map((swatch) => hueBucket(hexToRgb(swatch.color))),
    );
    expect(hueBuckets.size).toBeGreaterThanOrEqual(6);
  });

  it("wraps indexes deterministically and exports css variables", () => {
    expect(categoricalSwatch(0).name).toBe(categorical12[0].name);
    expect(categoricalSwatch(12).name).toBe(categorical12[0].name);
    expect(categoricalSwatch(-1).name).toBe(categorical12[11].name);
    expect(categoricalCssVars()["--category-12"]).toBe(categorical12[11].color);
  });
});

function hexToRgb(hex: string) {
  const normalized = hex.replace("#", "");
  return {
    b: Number.parseInt(normalized.slice(4, 6), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    r: Number.parseInt(normalized.slice(0, 2), 16),
  };
}

function hueBucket({ r, g, b }: { r: number; g: number; b: number }) {
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
  const degrees = Math.round(hue * 60);
  return Math.floor(((degrees + 360) % 360) / 45);
}
