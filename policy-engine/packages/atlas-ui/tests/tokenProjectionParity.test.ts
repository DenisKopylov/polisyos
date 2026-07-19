import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  breakpointProjection,
  chartColorAliases,
  contrastModeDescriptors,
  densityModeDescriptors,
  motionDurations,
  motionModeDescriptors,
  printModeDescriptors,
  resolveThemeMode,
  semanticColorAliases,
  themeModeDescriptors,
  tokenProjectionManifest,
  zIndexLayers,
} from "../src/generated/tokens";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

describe("DTCG token projection parity", () => {
  it("preserves ADR-047 warm-dark values across DTCG projections", () => {
    expect(themeModeDescriptors.dark.tokens).toMatchObject({
      "--canvas": "#120f0e",
      "--ink": "#f5efe2",
      "--paper": "#1d1917",
      "--slate": "#bcae9d",
    });
    expect(themeModeDescriptors.dark.metaThemeColor).toBe("#120f0e");
    expect(themeModeDescriptors.light.metaThemeColor).toBe("#fbf8f2");
  });

  it("projects every live z-index alias exactly once", () => {
    expect(zIndexLayers).toEqual({
      base: 0,
      command: 600,
      dropdown: 50,
      modal: 300,
      overlay: 200,
      popover: 400,
      sticky: 100,
      toast: 500,
    });
    expect(new Set(Object.values(zIndexLayers))).toHaveLength(8);

    const css = fs.readFileSync(
      path.join(packageRoot, "src/generated/tokens.css"),
      "utf8",
    );
    for (const name of Object.keys(zIndexLayers)) {
      expect(css.match(new RegExp(`--z-${name}:`, "g"))).toHaveLength(1);
    }
  });

  it("preserves post-reference semantic aliases", () => {
    expect(semanticColorAliases).toMatchObject({
      "--color-action-destructive": "var(--danger)",
      "--color-action-primary": "var(--accent)",
      "--color-bounds-fill":
        "color-mix(in srgb, var(--accent) 8%, transparent)",
      "--color-evidence-verified": "var(--success)",
      "--color-governance-blocker": "var(--danger)",
      "--color-status-approved": "var(--success)",
      "--color-transport-degraded": "var(--warning)",
      "--color-transport-live": "var(--chart-secondary)",
      "--color-uncertainty-point-estimate": "var(--chart-primary)",
      "--color-waterfall-negative": "var(--chart-alert)",
    });
    expect(chartColorAliases).toEqual({
      alert: "var(--chart-alert)",
      axis: "var(--chart-axis)",
      grid: "var(--chart-grid)",
      neutral: "var(--chart-neutral)",
      primary: "var(--chart-primary)",
      secondary: "var(--chart-secondary)",
      success: "var(--chart-success)",
      tertiary: "var(--chart-tertiary)",
      warning: "var(--chart-warning)",
    });
  });

  it("switches comfortable compact and condensed density at runtime", () => {
    expect(densityModeDescriptors.comfortable).toMatchObject({
      attribute: "comfortable",
      tokens: {
        "--font-scale-step": 0,
        "--root-font-size": "16px",
        "--row-height-scale": 1,
        "--space-scale": 1,
      },
    });
    expect(densityModeDescriptors.compact).toMatchObject({
      attribute: "compact",
      tokens: {
        "--font-scale-step": -1,
        "--root-font-size": "15px",
        "--row-height-scale": 0.85,
        "--space-scale": 0.75,
      },
    });
    expect(densityModeDescriptors.condensed).toMatchObject({
      attribute: "condensed",
      tokens: {
        "--font-scale-step": -2,
        "--root-font-size": "14px",
        "--row-height-scale": 0.7,
        "--space-scale": 0.5,
      },
    });
  });

  it("projects the live five-tier breakpoint contract without the rejected taxonomy", () => {
    expect(breakpointProjection).toEqual({
      runtime: {
        compactMin: 768,
        expandedMin: 1281,
        mobileMax: 639,
        standardMin: 1024,
        tabletMin: 640,
      },
      tokens: { "2xl": 1536, lg: 1024, md: 768, sm: 640, xl: 1280 },
    });
    expect(breakpointProjection.tokens.xl).toBe(1280);
    expect(breakpointProjection.runtime.expandedMin).toBe(1281);
    expect(JSON.stringify(tokenProjectionManifest)).not.toContain(
      "responsive-breakpoint-taxonomy",
    );
  });

  it("round-trips light dark and system through the mode provider", () => {
    expect(resolveThemeMode("light", true)).toBe("light");
    expect(resolveThemeMode("dark", false)).toBe("dark");
    expect(resolveThemeMode("system", false)).toBe("light");
    expect(resolveThemeMode("system", true)).toBe("dark");
    expect(themeModeDescriptors.system).toEqual({
      attribute: "system",
      dark: "dark",
      light: "light",
      mediaQuery: "(prefers-color-scheme: dark)",
    });
  });

  it("applies forced-color and contrast modes without semantic color dependence", () => {
    expect(contrastModeDescriptors.high).toMatchObject({
      attribute: "high",
      backdropFilter: "none",
      semanticColorIndependent: true,
      tokens: {
        "--accent": "Highlight",
        "--canvas": "Canvas",
        "--danger": "LinkText",
        "--ink": "CanvasText",
      },
    });
    expect(contrastModeDescriptors.forcedColors).toMatchObject({
      backdropFilter: "none",
      mediaQuery: "(forced-colors: active)",
      semanticColorIndependent: true,
      tokens: {
        "--chart-alert": "Mark",
        "--chart-primary": "LinkText",
        "--chart-secondary": "CanvasText",
      },
    });
  });

  it("removes nonessential motion for reduced-motion modes", () => {
    expect(motionDurations).toEqual({
      css: {
        fastMs: 160,
        hopMs: 500,
        instantMs: 80,
        moderateMs: 240,
        slowMs: 360,
      },
      helper: {
        emphasisMs: 400,
        fastMs: 160,
        moderateMs: 180,
        slowMs: 240,
      },
    });
    expect(motionModeDescriptors.reduced).toMatchObject({
      attribute: "reduce",
      mediaQuery: "(prefers-reduced-motion: reduce)",
      nonessentialTransform: "none",
      reduced: true,
      tokens: {
        "--animation-duration": "0.01ms",
        "--transition-duration": "0.01ms",
      },
    });
  });

  it("projects print tokens and export behavior", () => {
    expect(printModeDescriptors.export).toMatchObject({
      mediaQuery: "print",
      page: { margin: "2.5cm 2cm", size: "A4" },
      tokens: {
        "--print-ink": "#111111",
        "--print-line": "#b8b8b8",
        "--print-muted": "#444444",
      },
    });
    expect(printModeDescriptors.export.hideSelectors).toContain(
      '[data-print-hidden="true"]',
    );
    expect(printModeDescriptors.export.keepTogetherSelectors).toContain(
      '[data-print-keep-together="true"]',
    );

    const printSource = JSON.parse(
      fs.readFileSync(
        path.join(packageRoot, "tokens/modes/print.tokens.json"),
        "utf8",
      ),
    ) as {
      $extensions: {
        "org.polisyos.atlas": {
          projection: {
            printMode: {
              export: {
                hideSelectors?: unknown;
                keepTogetherSelectors?: unknown;
                rules: Record<string, { selectors: Record<string, string> }>;
              };
            };
          };
        };
      };
    };
    const printExport =
      printSource.$extensions["org.polisyos.atlas"].projection.printMode.export;
    expect(printExport).not.toHaveProperty("hideSelectors");
    expect(printExport).not.toHaveProperty("keepTogetherSelectors");
    expect(printModeDescriptors.export.hideSelectors).toEqual(
      Object.values(printExport.rules.hide.selectors),
    );
    expect(printModeDescriptors.export.keepTogetherSelectors).toEqual([
      ...Object.values(printExport.rules.keepTogether.selectors),
      ...Object.values(printExport.rules.charts.selectors),
    ]);
  });
});
