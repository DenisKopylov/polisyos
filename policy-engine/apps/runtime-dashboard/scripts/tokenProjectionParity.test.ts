import { readFileSync } from "node:fs";
import postcss, {
  type AnyNode,
  type AtRule,
  type Declaration,
  type Rule,
} from "postcss";
import { describe, expect, it } from "vitest";

import {
  breakpointProjection,
  chartColorAliases,
  contrastModeDescriptors,
  densityModeDescriptors,
  motionDurations,
  motionModeDescriptors,
  printModeDescriptors,
  semanticColorAliases,
  themeModeDescriptors,
  zIndexLayers,
} from "@polisyos/atlas-ui";

import { SUPPORTED_DENSITIES } from "@/app/providers/DensityProvider";
import { SUPPORTED_THEMES } from "@/app/providers/ThemeProvider";
import { chartTheme } from "@/shared/ui/chartTheme";
import { duration } from "@/shared/ui/motion";
import {
  breakpointTokens,
  densityScale,
  semanticTokens,
} from "@/shared/ui/tokens/designTokens";

function readSource(relativePath: string) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function expectCssToken(source: string, name: string, value: string | number) {
  expect(source).toContain(`${name}: ${value};`);
}

function normalizeCssValue(value: string | number) {
  return String(value)
    .replace(/\s+/g, " ")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .trim();
}

function mediaAncestor(rule: Rule): string | null {
  let parent: AnyNode | undefined = rule.parent;
  while (parent) {
    if (parent.type === "atrule" && parent.name === "media") {
      return parent.params;
    }
    parent = parent.parent;
  }
  return null;
}

function layerAncestor(rule: Rule): string | null {
  let parent: AnyNode | undefined = rule.parent;
  while (parent) {
    if (parent.type === "atrule" && parent.name === "layer") {
      return parent.params;
    }
    parent = parent.parent;
  }
  return null;
}

function selectorParts(selector: string) {
  return selector
    .split(",")
    .map((part) => part.replace(/\s+/g, " ").trim())
    .sort();
}

function customProperties(
  sources: readonly string[],
  selector: string,
  media: string | null = null,
) {
  const result: Record<string, string> = {};
  for (const source of sources) {
    postcss.parse(source).walkRules((rule) => {
      if (
        mediaAncestor(rule) !== media ||
        !selectorParts(rule.selector).includes(selector)
      ) {
        return;
      }
      rule.walkDecls((declaration) => {
        if (declaration.prop.startsWith("--")) {
          result[declaration.prop] = normalizeCssValue(declaration.value);
        }
      });
    });
  }
  return result;
}

function projectedTokens(tokens: Record<string, string | number | boolean>) {
  return Object.fromEntries(
    Object.entries(tokens).map(([name, value]) => [
      name,
      normalizeCssValue(String(value)),
    ]),
  );
}

function expectTokenSubset(
  tokens: Record<string, string | number | boolean>,
  live: Record<string, string>,
) {
  const projected = projectedTokens(tokens);
  expect(Object.keys(projected).sort()).toEqual(
    Object.keys(projected)
      .filter((name) => Object.hasOwn(live, name))
      .sort(),
  );
  expect(
    Object.fromEntries(
      Object.keys(projected).map((name) => [name, live[name]]),
    ),
  ).toEqual(projected);
}

function expectExactTokens(
  tokens: Record<string, string | number | boolean>,
  live: Record<string, string>,
) {
  expect(projectedTokens(tokens)).toEqual(live);
}

function declarations(rule: Rule, includeCustomProperties: boolean) {
  return Object.fromEntries(
    rule.nodes
      .filter(
        (node): node is Declaration =>
          node.type === "decl" &&
          (includeCustomProperties || !node.prop.startsWith("--")),
      )
      .map((declaration) => [
        declaration.prop,
        `${normalizeCssValue(declaration.value)}${declaration.important ? " !important" : ""}`,
      ])
      .sort(([left], [right]) => left.localeCompare(right)),
  );
}

function mediaRuleMap(
  sources: readonly string[],
  media: string,
  includeCustomProperties = false,
) {
  const result: Record<string, Record<string, string>> = {};
  for (const source of sources) {
    postcss.parse(source).walkRules((rule) => {
      if (mediaAncestor(rule) !== media) {
        return;
      }
      const ruleDeclarations = declarations(rule, includeCustomProperties);
      if (Object.keys(ruleDeclarations).length > 0) {
        result[selectorParts(rule.selector).join(",")] = ruleDeclarations;
      }
    });
  }
  return result;
}

function contextualRuleMap(
  sources: readonly string[],
  media: string | null,
  includeCustomProperties = false,
) {
  const result: Record<string, Record<string, string>> = {};
  for (const source of sources) {
    postcss.parse(source).walkRules((rule) => {
      if (mediaAncestor(rule) !== media) return;
      const ruleDeclarations = declarations(rule, includeCustomProperties);
      if (Object.keys(ruleDeclarations).length === 0) return;
      const key = `${layerAncestor(rule) ?? "unlayered"}|${selectorParts(
        rule.selector,
      ).join(",")}`;
      result[key] = { ...result[key], ...ruleDeclarations };
    });
  }
  return result;
}

function orderedContextRules(
  sources: readonly string[],
  media: string | null,
  includeCustomProperties = false,
) {
  const contexts: Record<
    string,
    Array<{
      declarations: Record<string, string>;
      selectors: string[];
    }>
  > = {};
  for (const source of sources) {
    postcss.parse(source).walkRules((rule) => {
      if (mediaAncestor(rule) !== media) return;
      const ruleDeclarations = declarations(rule, includeCustomProperties);
      if (Object.keys(ruleDeclarations).length === 0) return;
      const layer = layerAncestor(rule) ?? "unlayered";
      (contexts[layer] ??= []).push({
        declarations: ruleDeclarations,
        selectors: selectorParts(rule.selector),
      });
    });
  }
  return contexts;
}

function nonMediaRuleMap(sources: readonly string[]) {
  const result: Record<string, Record<string, string>> = {};
  for (const source of sources) {
    postcss.parse(source).walkRules((rule) => {
      if (mediaAncestor(rule) !== null) {
        return;
      }
      const ruleDeclarations = declarations(rule, false);
      if (Object.keys(ruleDeclarations).length > 0) {
        result[selectorParts(rule.selector).join(",")] = ruleDeclarations;
      }
    });
  }
  return result;
}

function ruleContextForProperty(source: string, property: string) {
  const contexts: Array<{
    layer: string | null;
    media: string | null;
    selectors: string[];
  }> = [];
  postcss.parse(source).walkRules((rule) => {
    if (
      rule.nodes.some((node) => node.type === "decl" && node.prop === property)
    ) {
      contexts.push({
        layer: layerAncestor(rule),
        media: mediaAncestor(rule),
        selectors: selectorParts(rule.selector),
      });
    }
  });
  return contexts;
}

function selectedNonMediaRules(
  sources: readonly string[],
  selectors: readonly string[],
) {
  return Object.fromEntries(
    Object.entries(nonMediaRuleMap(sources)).filter(([selector]) =>
      selectors.includes(selector),
    ),
  );
}

function pageRule(source: string) {
  const result: Record<string, string> = {};
  postcss.parse(source).walkAtRules("page", (rule: AtRule) => {
    rule.walkDecls((declaration) => {
      result[declaration.prop] = normalizeCssValue(declaration.value);
    });
  });
  return result;
}

const stylesCss = readSource("../src/styles.css");
const lightThemeCss = readSource("../src/styles/theme-light.css");
const darkThemeCss = readSource("../src/styles/theme-dark.css");
const highContrastCss = readSource("../src/styles/theme-high-contrast.css");
const mediaCss = readSource("../src/styles/media.css");
const motionCss = readSource("../src/styles/motion.css");
const printCss = readSource("../src/styles/print.css");
const generatedCss = readSource(
  "../../../packages/atlas-ui/src/generated/tokens.css",
);

const DEFERRED_COMPONENT_TOKENS = [
  "--chip-bg",
  "--chip-border-color",
  "--chip-ink",
  "--deck-card-bg",
  "--deck-card-border-color",
  "--deck-card-label-color",
  "--ghost-bg",
  "--ghost-bg-hover",
  "--ghost-border-color",
  "--input-bg",
  "--input-border-color",
  "--input-rim-light",
  "--locale-active-border",
  "--locale-active-end",
  "--locale-active-start",
  "--metric-bg",
  "--metric-border-color",
  "--metric-label-color",
  "--page-glow-ember",
  "--page-glow-teal",
  "--page-gradient-end",
  "--page-gradient-mid",
  "--page-gradient-start",
  "--panel-border-color",
  "--rail-active-bg",
  "--rail-active-ink",
  "--rail-border",
  "--rail-card-bg",
  "--rail-card-border",
  "--rail-hover-bg",
  "--rail-ink",
  "--rail-link",
  "--rail-muted-ink",
  "--rail-surface",
  "--rail-surface-end",
  "--rail-surface-start",
  "--rim-light",
  "--rim-light-color",
  "--shell-border",
  "--shell-glass-base",
  "--shell-glass-end",
  "--shell-glass-start",
  "--status-fail-bg",
  "--status-neutral-bg",
  "--status-neutral-fg",
  "--status-ok-bg",
  "--status-warn-bg",
  "--status-warn-fg",
  "--surface-gradient-end",
  "--surface-gradient-start",
] as const;

function admittedThemeTokens(live: Record<string, string>) {
  return Object.fromEntries(
    Object.entries(live).filter(
      ([name]) =>
        !DEFERRED_COMPONENT_TOKENS.includes(
          name as (typeof DEFERRED_COMPONENT_TOKENS)[number],
        ),
    ),
  );
}

describe("DTCG token projection parity", () => {
  it("preserves ADR-047 warm-dark values across DTCG projections", () => {
    expect(themeModeDescriptors.dark.metaThemeColor).toBe("#120f0e");
    expect(themeModeDescriptors.dark.tokens).toMatchObject({
      "--canvas": "#120f0e",
      "--ink": "#f5efe2",
      "--paper": "#1d1917",
      "--slate": "#bcae9d",
    });

    expectExactTokens(
      themeModeDescriptors.dark.tokens,
      admittedThemeTokens(
        customProperties([darkThemeCss], ':root[data-theme="dark"]'),
      ),
    );
    expectExactTokens(
      themeModeDescriptors.light.tokens,
      admittedThemeTokens(
        customProperties([lightThemeCss], ':root[data-theme="light"]'),
      ),
    );
    expect(ruleContextForProperty(generatedCss, "--canvas")).toContainEqual({
      layer: "base",
      media: null,
      selectors: [":root", ':root[data-theme="light"]'],
    });
    expect(ruleContextForProperty(generatedCss, "--slate")).toContainEqual({
      layer: "base",
      media: null,
      selectors: [':root[data-theme="dark"]'],
    });
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

    for (const [name, value] of Object.entries(zIndexLayers)) {
      const customProperty = `--z-${name}`;
      expectCssToken(stylesCss, customProperty, value);
      expect(
        stylesCss.match(new RegExp(`${customProperty}:`, "g")),
      ).toHaveLength(1);
    }
  });

  it("preserves post-reference semantic aliases", () => {
    const liveSemanticAliases = Object.values(semanticTokens).flatMap((group) =>
      Object.values(group).map((token) => token.cssVar),
    );

    expect(Object.keys(semanticColorAliases)).toEqual(
      expect.arrayContaining(liveSemanticAliases),
    );
    expect(semanticColorAliases["--color-transport-live"]).toBe(
      "var(--chart-secondary)",
    );
    expectTokenSubset(
      semanticColorAliases,
      customProperties([lightThemeCss], ':root[data-theme="light"]'),
    );
    expect(chartColorAliases).toEqual(chartTheme);
  });

  it("switches comfortable compact and condensed density at runtime", () => {
    expect(Object.keys(densityModeDescriptors)).toEqual(SUPPORTED_DENSITIES);

    for (const density of SUPPORTED_DENSITIES) {
      const descriptor = densityModeDescriptors[density];
      const live = densityScale[density];
      expect(descriptor.attribute).toBe(density);
      expect(descriptor.tokens).toMatchObject({
        "--font-scale-step": live.fontStep,
        "--row-height-scale": live.rowHeight,
        "--space-scale": live.space,
      });
      expectExactTokens(
        descriptor.tokens,
        customProperties(
          [readSource(`../src/styles/density-${density}.css`)],
          `:root[data-density="${density}"]`,
        ),
      );
      expect(
        ruleContextForProperty(generatedCss, "--space-scale"),
      ).toContainEqual({
        layer: "base",
        media: null,
        selectors:
          density === "comfortable"
            ? [":root", ':root[data-density="comfortable"]']
            : [`:root[data-density="${density}"]`],
      });
    }
  });

  it("projects the live five-tier breakpoint contract without the rejected taxonomy", () => {
    expect(breakpointProjection.tokens).toEqual(breakpointTokens);
    expect(breakpointProjection.runtime).toEqual({
      compactMin: 768,
      expandedMin: 1281,
      mobileMax: 639,
      standardMin: 1024,
      tabletMin: 640,
    });
    expect(breakpointProjection.tokens.xl).toBe(1280);
    expect(breakpointProjection.runtime.expandedMin).toBe(1281);
  });

  it("round-trips light dark and system through the living mode owner", () => {
    expect(Object.keys(themeModeDescriptors)).toEqual(SUPPORTED_THEMES);
    expect(themeModeDescriptors.light.metaThemeColor).toBe("#fbf8f2");
    expect(themeModeDescriptors.system).toMatchObject({
      attribute: "system",
      dark: "dark",
      light: "light",
      mediaQuery: "(prefers-color-scheme: dark)",
    });
  });

  it("applies forced-color and contrast modes without semantic color dependence", () => {
    expect(contrastModeDescriptors.more).toMatchObject({
      attribute: "more",
      backdropFilter: "none",
      semanticColorIndependent: true,
    });
    expect(contrastModeDescriptors.forcedColors).toMatchObject({
      backdropFilter: "none",
      mediaQuery: "(forced-colors: active)",
      semanticColorIndependent: true,
    });
    expectExactTokens(
      contrastModeDescriptors.high.tokens,
      customProperties([highContrastCss], ':root[data-contrast="high"]'),
    );
    expectExactTokens(
      contrastModeDescriptors.forcedColors.tokens,
      customProperties(
        [highContrastCss, mediaCss],
        ":root",
        "(forced-colors: active)",
      ),
    );
    expectExactTokens(
      contrastModeDescriptors.more.tokens,
      customProperties([stylesCss], ":root", "(prefers-contrast: more)"),
    );
    expect(mediaRuleMap([generatedCss], "(prefers-contrast: more)")).toEqual(
      mediaRuleMap([stylesCss], "(prefers-contrast: more)"),
    );
    const moreManualSelectors = [
      ':root[data-contrast="more"] .brand-glyph,:root[data-contrast="more"] .glyph,:root[data-contrast="more"] [data-glyph-name]',
      ':root[data-contrast="more"] .provenance-strip li + li',
    ];
    expect(selectedNonMediaRules([generatedCss], moreManualSelectors)).toEqual(
      selectedNonMediaRules([stylesCss], moreManualSelectors),
    );
    const liveHighRules = nonMediaRuleMap([highContrastCss]);
    expect(
      selectedNonMediaRules([generatedCss], Object.keys(liveHighRules)),
    ).toEqual(liveHighRules);
    expect(
      orderedContextRules([generatedCss], "(forced-colors: active)", true),
    ).toEqual(
      orderedContextRules(
        [highContrastCss, mediaCss, stylesCss],
        "(forced-colors: active)",
        true,
      ),
    );
  });

  it("removes nonessential motion while preserving both moderate aliases", () => {
    expect(motionDurations.css.moderateMs).toBe(240);
    expect(motionDurations.helper.moderateMs).toBe(180);
    expect(motionDurations.helper).toEqual({
      emphasisMs: duration.emphasis * 1_000,
      fastMs: duration.fast * 1_000,
      moderateMs: duration.moderate * 1_000,
      slowMs: duration.slow * 1_000,
    });
    const liveMotionTokens = customProperties([motionCss], ":root");
    expectExactTokens(
      motionModeDescriptors.default.tokens,
      Object.fromEntries(
        Object.entries(liveMotionTokens).filter(([name]) =>
          /--motion-(?:distance|duration|ease)-/.test(name),
        ),
      ),
    );
    expectCssToken(
      motionCss,
      "--motion-duration-moderate",
      `${motionDurations.css.moderateMs}ms`,
    );
    expectCssToken(
      stylesCss,
      "--motion-moderate",
      `${motionDurations.helper.moderateMs}ms`,
    );
    expect(motionModeDescriptors.reduced).toMatchObject({
      attribute: "reduce",
      mediaQuery: "(prefers-reduced-motion: reduce)",
      nonessentialTransform: "none",
      reduced: true,
    });
    expect(
      mediaRuleMap([generatedCss], "(prefers-reduced-motion: reduce)"),
    ).toEqual(
      mediaRuleMap([mediaCss, stylesCss], "(prefers-reduced-motion: reduce)"),
    );
    const manualReducedSelectors = [
      ':root[data-reduced-motion="reduce"] *,:root[data-reduced-motion="reduce"] *::after,:root[data-reduced-motion="reduce"] *::before',
      ':root[data-reduced-motion="reduce"] .hops',
      ':root[data-reduced-motion="reduce"] .hops + .hops-static-fallback',
    ];
    expect(
      selectedNonMediaRules([generatedCss], manualReducedSelectors),
    ).toEqual(selectedNonMediaRules([stylesCss], manualReducedSelectors));
  });

  it("projects print tokens and export behavior", () => {
    const descriptor = printModeDescriptors.export;
    expect(descriptor).toMatchObject({
      mediaQuery: "print",
      page: { margin: "2.5cm 2cm", size: "A4" },
    });
    expectExactTokens(
      descriptor.tokens,
      customProperties([printCss], ":root", "print"),
    );
    expect(pageRule(generatedCss)).toEqual(pageRule(printCss));
    expect(orderedContextRules([generatedCss], "print", true)).toEqual(
      orderedContextRules([mediaCss, printCss, stylesCss], "print", true),
    );
    expect(
      contextualRuleMap([generatedCss], null)["utilities|.media-print-only"],
    ).toEqual(
      contextualRuleMap([mediaCss], null)["utilities|.media-print-only"],
    );
  });

  it("detects same-context source-order drift that changes the cascade", () => {
    const documentCanvas =
      "@media print { html, body { color: var(--print-ink) !important; } }";
    const applicationBody =
      "@media print { body { color: black !important; } }";

    expect(
      contextualRuleMap([documentCanvas, applicationBody], "print", true),
    ).toEqual(
      contextualRuleMap([applicationBody, documentCanvas], "print", true),
    );
    expect(
      orderedContextRules([documentCanvas, applicationBody], "print", true),
    ).not.toEqual(
      orderedContextRules([applicationBody, documentCanvas], "print", true),
    );
  });

  it("rejects drift in an unlisted projected member while source markers remain", () => {
    const entries = Object.entries(themeModeDescriptors.dark.tokens);
    const [name] = entries[Math.floor(entries.length * 0.73)];
    const corrupted = {
      ...themeModeDescriptors.dark.tokens,
      [name]: "corrupted-but-still-valid-css",
    };
    const live = customProperties([darkThemeCss], ':root[data-theme="dark"]');

    expect(() =>
      expectExactTokens(corrupted, admittedThemeTokens(live)),
    ).toThrow();
  });
});
