import AxePlaywrightBuilder from "@axe-core/playwright";
import type { AxeResults, Result } from "axe-core";
import { expect, test } from "@playwright/test";

import { WCAG_AA_TAGS } from "@/test/a11yTags";
import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../../../e2e/helpers/runtime-dashboard";
import { openCapabilityDiscovery } from "../../../e2e/helpers/capabilityDiscovery";

type RgbColor = [number, number, number];

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

function parseRgbColor(input: string): RgbColor {
  const normalized = input.replace(/\s+/g, " ").trim();
  const hexMatch = normalized.match(/^#([\da-f]{3}|[\da-f]{6})$/i);

  if (hexMatch) {
    const hex = hexMatch[1];
    const expanded =
      hex.length === 3
        ? hex
            .split("")
            .map((value) => `${value}${value}`)
            .join("")
        : hex;

    return [
      Number.parseInt(expanded.slice(0, 2), 16),
      Number.parseInt(expanded.slice(2, 4), 16),
      Number.parseInt(expanded.slice(4, 6), 16),
    ];
  }

  const match = normalized.match(/^rgba?\(([\d.]+), ([\d.]+), ([\d.]+)/);

  if (!match) {
    throw new Error(`Unsupported color format: ${input}`);
  }

  return [
    Number.parseFloat(match[1]),
    Number.parseFloat(match[2]),
    Number.parseFloat(match[3]),
  ];
}

function simulateColor(
  color: RgbColor,
  matrix: readonly (readonly number[])[],
): RgbColor {
  const [red, green, blue] = color;

  return [
    Math.round(red * matrix[0][0] + green * matrix[0][1] + blue * matrix[0][2]),
    Math.round(red * matrix[1][0] + green * matrix[1][1] + blue * matrix[1][2]),
    Math.round(red * matrix[2][0] + green * matrix[2][1] + blue * matrix[2][2]),
  ];
}

function colorDistance(left: RgbColor, right: RgbColor) {
  return Math.hypot(left[0] - right[0], left[1] - right[1], left[2] - right[2]);
}

function countAxeNodes(results: Result[]): number {
  return results.reduce((total, result) => total + result.nodes.length, 0);
}

function parseAxeRatio(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== "string") {
    return null;
  }
  const match = /^(\d+(?:\.\d+)?):1$/.exec(value);
  return match ? Number(match[1]) : null;
}

function numericContrastPasses(results: AxeResults) {
  return results.passes.flatMap((result) =>
    result.nodes.flatMap((node) =>
      [...node.any, ...node.all, ...node.none].flatMap((check) => {
        const data = check.data as Record<string, unknown> | null;
        if (!data || !("contrastRatio" in data)) {
          return [];
        }
        const contrastRatio = parseAxeRatio(data.contrastRatio);
        const expectedContrastRatio = parseAxeRatio(data.expectedContrastRatio);
        return contrastRatio === null || expectedContrastRatio === null
          ? []
          : [{ contrastRatio, expectedContrastRatio }];
      }),
    ),
  );
}

test.describe("runtime-dashboard color blind simulation", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("keeps signal pairs distinguishable for deuteranope, protanope, and tritanope viewers", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();

    await page.goto(`/runs/${metadata.core_run_id}/report`);
    await waitForDashboardSurface(page, "run-report");

    const axeResults = await new AxePlaywrightBuilder({ page })
      .withTags([...WCAG_AA_TAGS])
      .analyze();
    expect(axeResults.violations).toEqual([]);

    const colors = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement);
      return {
        ember: styles.getPropertyValue("--ember"),
        gold: styles.getPropertyValue("--gold"),
        slate: styles.getPropertyValue("--slate"),
        teal: styles.getPropertyValue("--teal"),
      };
    });

    const parsedColors = {
      ember: parseRgbColor(colors.ember),
      gold: parseRgbColor(colors.gold),
      slate: parseRgbColor(colors.slate),
      teal: parseRgbColor(colors.teal),
    };

    for (const [simulationName, matrix] of Object.entries(
      COLOR_BLIND_MATRICES,
    )) {
      const goldVsEmber = colorDistance(
        simulateColor(parsedColors.gold, matrix),
        simulateColor(parsedColors.ember, matrix),
      );
      const tealVsSlate = colorDistance(
        simulateColor(parsedColors.teal, matrix),
        simulateColor(parsedColors.slate, matrix),
      );

      expect
        .soft(goldVsEmber, `${simulationName} should preserve gold vs ember`)
        .toBeGreaterThanOrEqual(15);
      expect
        .soft(tealVsSlate, `${simulationName} should preserve teal vs slate`)
        .toBeGreaterThanOrEqual(20);
    }
  });

  test("DS10 capability discovery candidate clothing passes opaque-background WCAG AA contrast", async ({
    page,
  }) => {
    const panel = await openCapabilityDiscovery(page, "executable");
    const axeResults = await new AxePlaywrightBuilder({ page })
      .include('[data-testid="capability-discovery-panel"]')
      .withTags([...WCAG_AA_TAGS])
      .analyze();
    expect(axeResults.violations).toEqual([]);

    const candidateBackdrop = panel.locator(
      '[data-capability-candidate-backdrop="true"]',
    );
    await expect(candidateBackdrop).toHaveCount(1);
    const candidateBadge = candidateBackdrop.getByText(
      "Candidate · bridge_missing",
      { exact: true },
    );
    await expect(candidateBadge).toBeVisible();
    const renderedBackdrop = await candidateBackdrop.evaluate((element) => {
      const style = getComputedStyle(element);
      const canvas = document.createElement("canvas");
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        throw new Error("The browser did not provide a 2D canvas context.");
      }
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = style.backgroundColor;
      context.fillRect(0, 0, 1, 1);
      return {
        alpha: context.getImageData(0, 0, 1, 1).data[3],
        backgroundImage: style.backgroundImage,
      };
    });
    expect(renderedBackdrop).toEqual({ alpha: 255, backgroundImage: "none" });

    const contrastResults = await new AxePlaywrightBuilder({ page })
      .include('[data-capability-candidate-backdrop="true"]')
      .options({
        elementRef: true,
        resultTypes: ["passes", "violations", "incomplete"],
        runOnly: { type: "rule", values: ["color-contrast"] },
      })
      .analyze();
    expect(countAxeNodes(contrastResults.violations)).toBe(0);
    expect(countAxeNodes(contrastResults.incomplete)).toBe(0);
    const contrastPasses = numericContrastPasses(contrastResults);
    expect(contrastPasses.length).toBeGreaterThan(0);
    for (const pass of contrastPasses) {
      expect(pass.contrastRatio).toBeGreaterThanOrEqual(
        pass.expectedContrastRatio,
      );
    }
  });
});
