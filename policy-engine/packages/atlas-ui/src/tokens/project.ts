import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE_DIRECTORIES = ["tokens/source", "tokens/modes"] as const;
const GENERATED_DIRECTORY = "src/generated";
const GENERATED_FILES = [
  "figma.json",
  "manifest.json",
  "tailwind.ts",
  "tokens.css",
  "tokens.ts",
] as const;

type JsonPrimitive = boolean | number | string | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
type TokenRecord = Record<string, JsonValue>;

export type TokenProjectionCheck = {
  diagnostics: string[];
  ok: boolean;
};

type ProjectionSource = {
  relativePath: string;
  source: TokenRecord;
  text: string;
};

type ProjectionOutputs = Record<(typeof GENERATED_FILES)[number], string>;

const DTCG_SCHEMA = "https://www.designtokens.org/schemas/2025.10/format.json";
const ATLAS_EXTENSION = "org.polisyos.atlas";
const SUPPORTED_DTCG_TYPES = new Set([
  "color",
  "cubicBezier",
  "dimension",
  "duration",
  "number",
]);

function finiteNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${label} must contain a finite number`);
  }
  return value;
}

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function rejectUnknownFields(
  value: Record<string, unknown>,
  allowed: readonly string[],
  label: string,
): void {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw new TypeError(`${label}: unsupported ${unknown.join(", ")}`);
  }
}

function validateDtcgMetadata(
  value: Record<string, unknown>,
  label: string,
): void {
  if (
    value.$description !== undefined &&
    typeof value.$description !== "string"
  ) {
    throw new TypeError(`${label}: $description must be a string`);
  }
  if (
    value.$deprecated !== undefined &&
    typeof value.$deprecated !== "boolean" &&
    typeof value.$deprecated !== "string"
  ) {
    throw new TypeError(`${label}: $deprecated must be a boolean or string`);
  }
  if (value.$extensions !== undefined) {
    objectValue(value.$extensions, `${label}: $extensions`);
  }
}

function validateDtcgValue(type: string, value: unknown, tokenPath: string) {
  if (type === "number") {
    finiteNumber(value, `${tokenPath}: number token`);
    return;
  }
  if (type === "cubicBezier") {
    if (
      !Array.isArray(value) ||
      value.length !== 4 ||
      value.some(
        (component) =>
          typeof component !== "number" || !Number.isFinite(component),
      )
    ) {
      throw new TypeError(
        `${tokenPath}: cubicBezier token must contain four finite numbers`,
      );
    }
    if (value[0] < 0 || value[0] > 1 || value[2] < 0 || value[2] > 1) {
      throw new TypeError(
        `${tokenPath}: cubicBezier x coordinates must be between zero and one`,
      );
    }
    return;
  }

  const composite = objectValue(value, `${tokenPath}: ${type} token`);
  if (type === "dimension" || type === "duration") {
    rejectUnknownFields(
      composite,
      ["unit", "value"],
      `${tokenPath}: unsupported ${type} value fields`,
    );
    finiteNumber(composite.value, `${tokenPath}: ${type} token value`);
    const allowedUnits = type === "duration" ? ["ms", "s"] : ["px", "rem"];
    if (
      typeof composite.unit !== "string" ||
      !allowedUnits.includes(composite.unit)
    ) {
      throw new TypeError(
        `${tokenPath}: ${type} token unit must be ${allowedUnits.join(" or ")}`,
      );
    }
    return;
  }

  rejectUnknownFields(
    composite,
    ["alpha", "colorSpace", "components", "hex"],
    `${tokenPath}: unsupported color value fields`,
  );

  if (composite.colorSpace !== "srgb") {
    throw new TypeError(`${tokenPath}: color token must use srgb`);
  }
  if (
    !Array.isArray(composite.components) ||
    composite.components.length !== 3 ||
    composite.components.some(
      (component) =>
        component !== "none" &&
        (typeof component !== "number" ||
          !Number.isFinite(component) ||
          component < 0 ||
          component > 1),
    )
  ) {
    throw new TypeError(
      `${tokenPath}: color token must contain three srgb components`,
    );
  }
  if (
    composite.alpha !== undefined &&
    (typeof composite.alpha !== "number" ||
      !Number.isFinite(composite.alpha) ||
      composite.alpha < 0 ||
      composite.alpha > 1)
  ) {
    throw new TypeError(
      `${tokenPath}: color alpha must be between zero and one`,
    );
  }
  if (composite.hex !== undefined) {
    if (
      typeof composite.hex !== "string" ||
      !/^#[0-9a-f]{6}$/i.test(composite.hex)
    ) {
      throw new TypeError(
        `${tokenPath}: color hex must be a six-digit hex value`,
      );
    }
    if (composite.components.every((component) => component !== "none")) {
      const componentHex = (composite.components as number[])
        .map((component) =>
          Math.round(component * 255)
            .toString(16)
            .padStart(2, "0"),
        )
        .join("");
      if (composite.hex.toLowerCase() !== `#${componentHex}`) {
        throw new TypeError(
          `${tokenPath}: color hex must match its srgb components`,
        );
      }
    }
  }
}

function validateDtcgNode(
  value: unknown,
  tokenPath: string,
  isRoot = false,
): void {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`${tokenPath}: DTCG groups and tokens must be objects`);
  }
  const object = value as Record<string, unknown>;
  validateDtcgMetadata(object, tokenPath);
  const hasType = Object.hasOwn(object, "$type");
  const hasValue = Object.hasOwn(object, "$value");

  if (hasType !== hasValue) {
    throw new TypeError(
      `${tokenPath}: DTCG token must declare both $type and $value`,
    );
  }
  if (hasType && hasValue) {
    const type = object.$type;
    if (typeof type !== "string" || !SUPPORTED_DTCG_TYPES.has(type)) {
      throw new TypeError(
        `${tokenPath}: unsupported DTCG $type ${String(type)}`,
      );
    }
    const nestedSiblings = Object.keys(object).filter(
      (key) => !key.startsWith("$"),
    );
    if (nestedSiblings.length > 0) {
      throw new TypeError(
        `${tokenPath}: DTCG token must not contain nested siblings`,
      );
    }
    const unsupportedMetadata = Object.keys(object).filter(
      (key) =>
        key.startsWith("$") &&
        ![
          "$deprecated",
          "$description",
          "$extensions",
          "$type",
          "$value",
        ].includes(key),
    );
    if (unsupportedMetadata.length > 0) {
      throw new TypeError(
        `${tokenPath}: unsupported DTCG metadata ${unsupportedMetadata.join(", ")}`,
      );
    }
    validateDtcgValue(type, object.$value, tokenPath);
    return;
  }

  const allowedGroupMetadata = ["$deprecated", "$description", "$extensions"];
  if (isRoot) allowedGroupMetadata.push("$schema");
  const unsupportedGroupMetadata = Object.keys(object).filter(
    (key) => key.startsWith("$") && !allowedGroupMetadata.includes(key),
  );
  if (unsupportedGroupMetadata.length > 0) {
    throw new TypeError(
      `${tokenPath}: unsupported DTCG group metadata ${unsupportedGroupMetadata.join(", ")}`,
    );
  }
  const children = Object.entries(object).filter(
    ([key]) => !key.startsWith("$"),
  );
  if (children.length === 0 && !isRoot) {
    throw new TypeError(`${tokenPath}: DTCG group must contain a token`);
  }
  for (const [key, child] of children) {
    if (!/^[^${}.][^{}.]*$/.test(key)) {
      throw new TypeError(
        `${tokenPath}: DTCG token and group names must not start with $ or contain braces or periods`,
      );
    }
    validateDtcgNode(child, `${tokenPath}.${key}`);
  }
}

function asRecord(value: JsonValue | undefined, label: string): TokenRecord {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`${label} must be a token object`);
  }
  return value;
}

function asPrimitive(
  value: JsonValue | undefined,
  label: string,
): JsonPrimitive {
  if (Array.isArray(value) || (value !== null && typeof value === "object")) {
    throw new TypeError(`${label} must be a scalar token value`);
  }
  if (value === undefined) {
    throw new TypeError(`${label} is missing`);
  }
  return value;
}

function at(
  root: TokenRecord,
  label: string,
  ...segments: string[]
): JsonValue {
  let current: JsonValue = root;
  for (const segment of segments) {
    current = asRecord(current, label)[segment];
    if (current === undefined) {
      throw new TypeError(`${label} is missing ${segments.join(".")}`);
    }
  }
  return current;
}

function atlasTokenCssValue(object: Record<string, unknown>): unknown {
  const extensions = object.$extensions;
  if (extensions === undefined) return undefined;
  const extensionRoot = objectValue(extensions, "DTCG token $extensions");
  const atlas = extensionRoot[ATLAS_EXTENSION];
  if (atlas === undefined) return undefined;
  return objectValue(atlas, `DTCG token ${ATLAS_EXTENSION}`).cssValue;
}

function unwrapToken(object: Record<string, unknown>): JsonValue {
  const cssValue = atlasTokenCssValue(object);
  const type = String(object.$type);
  const value = object.$value;
  let canonical: JsonValue | undefined;
  if (type === "number") canonical = value as number;
  if (type === "dimension" || type === "duration") {
    const composite = objectValue(value, `${type} value`);
    canonical = `${String(composite.value)}${String(composite.unit)}`;
  } else if (type === "cubicBezier") {
    canonical = `cubic-bezier(${(value as number[]).join(", ")})`;
  } else if (type === "color") {
    const color = objectValue(value, "color value");
    const components = color.components as Array<number | "none">;
    const channels = components.map((component) =>
      component === "none" ? component : Math.round(component * 255),
    );
    const hasMissingComponent = components.includes("none");
    const alpha =
      color.alpha === undefined
        ? undefined
        : finiteNumber(color.alpha, "color alpha");
    canonical =
      alpha !== undefined
        ? `rgb(${channels.join(" ")} / ${String(alpha)})`
        : typeof color.hex === "string" && !hasMissingComponent
          ? color.hex
          : `rgb(${channels.join(" ")})`;
  }
  if (canonical === undefined) {
    throw new TypeError(`unsupported DTCG token type ${type}`);
  }
  if (cssValue === undefined) return canonical;
  if (typeof cssValue !== "string" || cssValue.length === 0) {
    throw new TypeError(`${ATLAS_EXTENSION}.cssValue must be a string`);
  }
  if (cssValue !== canonical) {
    throw new TypeError(
      `${ATLAS_EXTENSION}.cssValue must equal the canonical DTCG value`,
    );
  }
  return cssValue;
}

function unwrapDtcg(value: unknown): JsonValue {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  ) {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(unwrapDtcg);
  }
  if (typeof value !== "object") {
    throw new TypeError("DTCG source contains an unsupported value");
  }

  const object = value as Record<string, unknown>;
  if (Object.hasOwn(object, "$value")) {
    return unwrapToken(object);
  }

  return Object.fromEntries(
    Object.entries(object)
      .filter(([key]) => !key.startsWith("$"))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, child]) => [key, unwrapDtcg(child)]),
  );
}

function mergeProjection(
  standard: JsonValue,
  projection: JsonValue,
  label: string,
): JsonValue {
  const standardIsRecord =
    standard !== null &&
    !Array.isArray(standard) &&
    typeof standard === "object";
  const projectionIsRecord =
    projection !== null &&
    !Array.isArray(projection) &&
    typeof projection === "object";
  if (standardIsRecord && projectionIsRecord) {
    const result: TokenRecord = { ...standard };
    for (const [key, value] of Object.entries(projection)) {
      result[key] = Object.hasOwn(result, key)
        ? mergeProjection(result[key], value, `${label}.${key}`)
        : value;
    }
    return result;
  }
  if (JSON.stringify(standard) !== JSON.stringify(projection)) {
    throw new TypeError(`${label}: DTCG token conflicts with Atlas projection`);
  }
  return standard;
}

function atlasProjection(
  root: Record<string, unknown>,
  label: string,
): JsonValue {
  const extensions = objectValue(root.$extensions, `${label}.$extensions`);
  const atlas = objectValue(
    extensions[ATLAS_EXTENSION],
    `${label}.$extensions.${ATLAS_EXTENSION}`,
  );
  return (atlas.projection ?? {}) as JsonValue;
}

function flattenTokens(
  value: JsonValue,
  prefix = "",
  result: Record<string, JsonPrimitive> = {},
): Record<string, JsonPrimitive> {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  ) {
    result[prefix] = value;
    return result;
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) =>
      flattenTokens(child, `${prefix}.${index}`, result),
    );
    return result;
  }
  for (const [key, child] of Object.entries(value).sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    flattenTokens(child, prefix ? `${prefix}.${key}` : key, result);
  }
  return result;
}

async function readSources(packageRoot: string): Promise<ProjectionSource[]> {
  const relativePaths = (
    await Promise.all(
      SOURCE_DIRECTORIES.map(async (directory) => {
        const names = await fs.readdir(path.join(packageRoot, directory));
        return names
          .filter((name) => name.endsWith(".tokens.json"))
          .map((name) => `${directory}/${name}`);
      }),
    )
  )
    .flat()
    .sort();

  return Promise.all(
    relativePaths.map(async (relativePath) => {
      const text = await fs.readFile(
        path.join(packageRoot, relativePath),
        "utf8",
      );
      const raw = JSON.parse(text) as unknown;
      const root = objectValue(raw, relativePath);
      if (root.$schema !== DTCG_SCHEMA) {
        throw new TypeError(
          `${relativePath}: $schema must be the DTCG 2025.10 schema`,
        );
      }
      validateDtcgNode(root, relativePath, true);
      const parsed = mergeProjection(
        unwrapDtcg(root),
        atlasProjection(root, relativePath),
        relativePath,
      );
      return {
        relativePath,
        source: asRecord(parsed, relativePath),
        text,
      };
    }),
  );
}

function cssBlock(selector: string, tokens: TokenRecord): string {
  const declarations = Object.entries(tokens)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(
      ([name, value]) =>
        `  ${name}: ${String(asPrimitive(value, `${selector}.${name}`))};`,
    )
    .join("\n");
  return `${selector} {\n${declarations}\n}`;
}

function cssBehaviorRules(value: JsonValue | undefined, label: string) {
  const rules = asRecord(value, label);
  return Object.entries(rules)
    .map(([ruleName, ruleValue]) => {
      const rule = asRecord(ruleValue, `${label}.${ruleName}`);
      const selector = Object.hasOwn(rule, "selector")
        ? String(asPrimitive(rule.selector, `${label}.${ruleName}.selector`))
        : Object.entries(
            asRecord(rule.selectors, `${label}.${ruleName}.selectors`),
          )
            .map(([selectorName, selectorValue]) =>
              String(
                asPrimitive(
                  selectorValue,
                  `${label}.${ruleName}.selectors.${selectorName}`,
                ),
              ),
            )
            .join(",\n");
      return cssBlock(
        selector,
        asRecord(rule.declarations, `${label}.${ruleName}.declarations`),
      );
    })
    .join("\n\n");
}

function json(value: unknown): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function exportedConstant(name: string, value: unknown): string {
  return `export const ${name} = ${JSON.stringify(value, null, 2)} as const;\n`;
}

function sourceBySuffix(
  sources: ProjectionSource[],
  suffix: string,
): TokenRecord {
  const match = sources.find(({ relativePath }) =>
    relativePath.endsWith(suffix),
  );
  if (!match) {
    throw new TypeError(`missing token source ${suffix}`);
  }
  return match.source;
}

async function projectTokenOutputs(
  packageRoot: string,
): Promise<ProjectionOutputs> {
  const sources = await readSources(packageRoot);
  const sourceDigest = createHash("sha256")
    .update(
      sources
        .map(({ relativePath, text }) => `${relativePath}\0${text}`)
        .join("\0"),
    )
    .digest("hex");

  const primitive = sourceBySuffix(sources, "source/primitive.tokens.json");
  const responsive = sourceBySuffix(sources, "source/responsive.tokens.json");
  const semantic = sourceBySuffix(sources, "source/semantic.tokens.json");
  const dataViz = sourceBySuffix(sources, "source/data-viz.tokens.json");
  const theme = sourceBySuffix(sources, "source/theme.tokens.json");
  const light = sourceBySuffix(sources, "modes/light.tokens.json");
  const dark = sourceBySuffix(sources, "modes/dark.tokens.json");
  const system = sourceBySuffix(sources, "modes/system.tokens.json");
  const density = sourceBySuffix(sources, "modes/density.tokens.json");
  const contrast = sourceBySuffix(sources, "modes/contrast.tokens.json");
  const motion = sourceBySuffix(sources, "modes/motion.tokens.json");
  const print = sourceBySuffix(sources, "modes/print.tokens.json");

  const primitiveRoot = asRecord(
    at(primitive, "primitive", "primitive"),
    "primitive",
  );
  const lightRoot = asRecord(at(light, "light", "modeLight"), "modeLight");
  const darkRoot = asRecord(at(dark, "dark", "modeDark"), "modeDark");
  const systemRoot = asRecord(at(system, "system", "modeSystem"), "modeSystem");
  const densityRoot = asRecord(at(density, "density", "density"), "density");
  const contrastRoot = asRecord(
    at(contrast, "contrast", "contrast"),
    "contrast",
  );
  const motionRoot = asRecord(at(motion, "motion", "motionMode"), "motionMode");
  const printRoot = asRecord(at(print, "print", "printMode"), "printMode");
  const themeRoot = asRecord(at(theme, "theme", "theme"), "theme");

  const semanticRoot = asRecord(
    at(semantic, "semantic", "semantic"),
    "semantic",
  );
  const semanticColorAliases = asRecord(
    semanticRoot.lightColorAliases,
    "semantic.lightColorAliases",
  );
  const darkSemanticColorAliases = asRecord(
    semanticRoot.darkColorAliases,
    "semantic.darkColorAliases",
  );

  const themeMeta = asRecord(
    at(themeRoot, "theme.metaThemeColor", "metaThemeColor"),
    "theme.metaThemeColor",
  );
  const themeModeDescriptors = {
    light: {
      ...lightRoot,
      metaThemeColor: themeMeta.light,
      tokens: {
        ...asRecord(lightRoot.tokens, "modeLight.tokens"),
        ...semanticColorAliases,
      },
    },
    dark: {
      ...darkRoot,
      metaThemeColor: themeMeta.dark,
      tokens: {
        ...asRecord(darkRoot.tokens, "modeDark.tokens"),
        ...darkSemanticColorAliases,
      },
    },
    system: systemRoot,
  };
  const densityModeDescriptors = {
    comfortable: asRecord(densityRoot.comfortable, "density.comfortable"),
    compact: asRecord(densityRoot.compact, "density.compact"),
    condensed: asRecord(densityRoot.condensed, "density.condensed"),
  };
  const forcedColorsSource = asRecord(
    contrastRoot.forcedColors,
    "contrast.forcedColors",
  );
  const forcedUnlayered = asRecord(
    forcedColorsSource.unlayered,
    "contrast.forcedColors.unlayered",
  );
  const forcedLayers = asRecord(
    forcedColorsSource.layers,
    "contrast.forcedColors.layers",
  );
  const forcedBase = asRecord(
    forcedLayers.base,
    "contrast.forcedColors.layers.base",
  );
  const forcedComponents = asRecord(
    forcedLayers.components,
    "contrast.forcedColors.layers.components",
  );
  const forcedColors = {
    ...forcedColorsSource,
    tokens: {
      ...asRecord(
        forcedUnlayered.tokens,
        "contrast.forcedColors.unlayered.tokens",
      ),
      ...asRecord(
        forcedBase.tokens,
        "contrast.forcedColors.layers.base.tokens",
      ),
    },
  };
  const high = asRecord(contrastRoot.high, "contrast.high");
  const more = asRecord(contrastRoot.more, "contrast.more");
  const contrastModeDescriptors = {
    high,
    more,
    forcedColors,
  };
  const motionDurations = asRecord(
    at(primitiveRoot, "primitive.motion", "motion"),
    "primitive.motion",
  );
  const motionModeDescriptors = {
    default: asRecord(motionRoot.default, "motionMode.default"),
    reduced: asRecord(motionRoot.reduced, "motionMode.reduced"),
  };
  const printExport = asRecord(printRoot.export, "printMode.export");
  const printRules = asRecord(printExport.rules, "printMode.export.rules");
  const selectorsFromRule = (ruleName: string) =>
    Object.values(
      asRecord(
        asRecord(printRules[ruleName], `printMode.export.rules.${ruleName}`)
          .selectors,
        `printMode.export.rules.${ruleName}.selectors`,
      ),
    );
  const printExportDescriptor: TokenRecord = {
    ...printExport,
    hideSelectors: selectorsFromRule("hide"),
    keepTogetherSelectors: [
      ...selectorsFromRule("keepTogether"),
      ...selectorsFromRule("charts"),
    ],
  };
  const printModeDescriptors = {
    export: printExportDescriptor,
  };
  const breakpointProjection = {
    runtime: asRecord(
      at(responsive, "responsive.runtime", "responsive", "runtime"),
      "responsive.runtime",
    ),
    tokens: asRecord(
      at(responsive, "responsive.breakpoints", "responsive", "breakpoints"),
      "responsive.breakpoints",
    ),
  };
  const chartColorAliases = asRecord(
    at(dataViz, "dataViz.chartColorAliases", "dataViz", "chartColorAliases"),
    "dataViz.chartColorAliases",
  );
  const zIndexLayers = asRecord(
    at(primitiveRoot, "primitive.zIndex", "zIndex"),
    "primitive.zIndex",
  );

  const unwrappedSources = Object.fromEntries(
    sources.map(({ relativePath, source }) => [relativePath, source]),
  );
  const generatedTokens = flattenTokens(unwrappedSources);
  const tokenProjectionManifest = {
    schemaVersion: 1,
    sourceDigest,
    sourceFiles: sources.map(({ relativePath }) => relativePath),
    generatedFiles: GENERATED_FILES.map(
      (name) => `${GENERATED_DIRECTORY}/${name}`,
    ),
    retainedAsymmetries: {
      cssModerateMotionMs: at(
        motionDurations,
        "primitive.motion.css.moderateMs",
        "css",
        "moderateMs",
      ),
      helperModerateMotionMs: at(
        motionDurations,
        "primitive.motion.helper.moderateMs",
        "helper",
        "moderateMs",
      ),
      runtimeExpandedMin: breakpointProjection.runtime.expandedMin,
      tokenXl: breakpointProjection.tokens.xl,
    },
  };

  const generatedHeader = `// @generated by src/tokens/project.ts\n// source-digest: ${sourceDigest}\n`;
  const tokensTs =
    generatedHeader +
    [
      exportedConstant("generatedTokens", generatedTokens),
      exportedConstant("tokenProjectionManifest", tokenProjectionManifest),
      exportedConstant("themeModeDescriptors", themeModeDescriptors),
      exportedConstant("densityModeDescriptors", densityModeDescriptors),
      exportedConstant("contrastModeDescriptors", contrastModeDescriptors),
      exportedConstant("motionDurations", motionDurations),
      exportedConstant("motionModeDescriptors", motionModeDescriptors),
      exportedConstant("printModeDescriptors", printModeDescriptors),
      exportedConstant("breakpointProjection", breakpointProjection),
      exportedConstant("chartColorAliases", chartColorAliases),
      exportedConstant("semanticColorAliases", semanticColorAliases),
      exportedConstant("zIndexLayers", zIndexLayers),
      "export type ThemeModePreference = keyof typeof themeModeDescriptors;\n",
      'export type ResolvedThemeMode = Exclude<ThemeModePreference, "system">;\n',
      'export function resolveThemeMode(preference: ThemeModePreference, systemDark: boolean): ResolvedThemeMode {\n  return preference === "system" ? (systemDark ? "dark" : "light") : preference;\n}\n',
    ].join("\n");

  const rootCssTokens = {
    ...asRecord(themeModeDescriptors.light.tokens, "modeLight.tokens"),
    ...asRecord(
      asRecord(motionRoot.default, "motionMode.default").tokens,
      "motionMode.default.tokens",
    ),
    ...Object.fromEntries(
      Object.entries(zIndexLayers).map(([name, value]) => [
        `--z-${name}`,
        value,
      ]),
    ),
  };
  const baseCss = [
    cssBlock(':root,\n:root[data-theme="light"]', rootCssTokens),
    cssBlock(
      ':root[data-theme="dark"]',
      asRecord(themeModeDescriptors.dark.tokens, "modeDark.tokens"),
    ),
    ...Object.entries(densityModeDescriptors).map(([name, descriptor]) =>
      cssBlock(
        name === "comfortable"
          ? ':root,\n:root[data-density="comfortable"]'
          : `:root[data-density="${name}"]`,
        asRecord(descriptor.tokens, `density.${name}.tokens`),
      ),
    ),
    cssBlock(
      Object.entries(
        asRecord(high.rootSelectors, "contrast.high.rootSelectors"),
      )
        .map(([name, value]) =>
          String(asPrimitive(value, `contrast.high.rootSelectors.${name}`)),
        )
        .join(",\n"),
      asRecord(high.tokens, "contrast.high.tokens"),
    ),
    cssBehaviorRules(high.rules, "contrast.high.rules"),
    cssBlock(
      ':root[data-contrast="more"]',
      asRecord(more.tokens, "contrast.more.tokens"),
    ),
    cssBehaviorRules(more.manualRules, "contrast.more.manualRules"),
    `@media ${String(asPrimitive(more.mediaQuery, "contrast.more.mediaQuery"))} {\n${cssBlock(
      ":root",
      asRecord(more.tokens, "contrast.more.tokens"),
    )}\n\n${cssBehaviorRules(more.mediaRules, "contrast.more.mediaRules")}\n}`,
    `@media ${String(asPrimitive(forcedColorsSource.mediaQuery, "contrast.forcedColors.mediaQuery"))} {\n${cssBlock(
      ":root",
      asRecord(forcedBase.tokens, "contrast.forcedColors.layers.base.tokens"),
    )}\n\n${cssBehaviorRules(
      forcedBase.rules,
      "contrast.forcedColors.layers.base.rules",
    )}\n}`,
    `@media ${String(asPrimitive(motionModeDescriptors.reduced.mediaQuery, "motionMode.reduced.mediaQuery"))} {\n${cssBlock(
      ":root",
      asRecord(
        motionModeDescriptors.reduced.tokens,
        "motionMode.reduced.tokens",
      ),
    )}\n\n${cssBehaviorRules(motionModeDescriptors.reduced.mediaRules, "motionMode.reduced.mediaRules")}\n}`,
    cssBehaviorRules(
      motionModeDescriptors.reduced.manualRules,
      "motionMode.reduced.manualRules",
    ),
  ].join("\n\n");
  const css = [
    `/* @generated by src/tokens/project.ts */\n/* source-digest: ${sourceDigest} */`,
    `@layer base {\n${baseCss}\n}`,
    `@media ${String(asPrimitive(forcedColorsSource.mediaQuery, "contrast.forcedColors.mediaQuery"))} {\n${cssBlock(
      ":root",
      asRecord(
        forcedUnlayered.tokens,
        "contrast.forcedColors.unlayered.tokens",
      ),
    )}\n\n${cssBehaviorRules(
      forcedUnlayered.rules,
      "contrast.forcedColors.unlayered.rules",
    )}\n}`,
    `@layer components {\n@media ${String(asPrimitive(forcedColorsSource.mediaQuery, "contrast.forcedColors.mediaQuery"))} {\n${cssBehaviorRules(
      forcedComponents.rules,
      "contrast.forcedColors.layers.components.rules",
    )}\n}\n}`,
    `@layer utilities {\n${cssBehaviorRules(
      printModeDescriptors.export.utilityBaseRules,
      "printMode.export.utilityBaseRules",
    )}\n\n@media ${String(asPrimitive(printModeDescriptors.export.mediaQuery, "printMode.export.mediaQuery"))} {\n${cssBehaviorRules(
      printModeDescriptors.export.utilityRules,
      "printMode.export.utilityRules",
    )}\n}\n}`,
    `@page {\n  margin: ${String(asPrimitive(asRecord(printModeDescriptors.export.page, "printMode.export.page").margin, "printMode.export.page.margin"))};\n  size: ${String(asPrimitive(asRecord(printModeDescriptors.export.page, "printMode.export.page").size, "printMode.export.page.size"))};\n}`,
    `@media ${String(asPrimitive(printModeDescriptors.export.mediaQuery, "printMode.export.mediaQuery"))} {\n${cssBlock(
      ":root",
      asRecord(printModeDescriptors.export.tokens, "printMode.export.tokens"),
    )}\n\n${cssBehaviorRules(printModeDescriptors.export.rules, "printMode.export.rules")}\n\n${cssBehaviorRules(
      printModeDescriptors.export.applicationRules,
      "printMode.export.applicationRules",
    )}\n}`,
    "",
  ].join("\n\n");

  const tailwindProjection = {
    screens: Object.fromEntries(
      Object.entries(breakpointProjection.tokens).map(([name, value]) => [
        name,
        `${String(asPrimitive(value, `responsive.breakpoints.${name}`))}px`,
      ]),
    ),
    zIndex: zIndexLayers,
    colors: Object.fromEntries(
      Object.keys(semanticColorAliases).map((name) => [
        name.replace(/^--color-/, ""),
        `var(${name})`,
      ]),
    ),
  };
  const tailwindTs = `${generatedHeader}${exportedConstant(
    "tailwindTokenProjection",
    tailwindProjection,
  )}`;
  const figma = {
    $description: "Generated Atlas token exchange projection",
    $extensions: { "polisyos.sourceDigest": sourceDigest },
    tokens: generatedTokens,
  };

  return {
    "figma.json": json(figma),
    "manifest.json": json(tokenProjectionManifest),
    "tailwind.ts": tailwindTs,
    "tokens.css": `${css.trimEnd()}\n`,
    "tokens.ts": tokensTs,
  };
}

export async function checkTokenProjection(
  packageRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
  ),
): Promise<TokenProjectionCheck> {
  const expected = await projectTokenOutputs(packageRoot);
  const generatedRoot = path.join(packageRoot, GENERATED_DIRECTORY);
  const diagnostics: string[] = [];
  let actualNames: string[] = [];
  try {
    actualNames = (await fs.readdir(generatedRoot)).sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw error;
    }
  }

  for (const actualName of actualNames) {
    if (
      !GENERATED_FILES.includes(actualName as (typeof GENERATED_FILES)[number])
    ) {
      diagnostics.push(
        `unexpected generated output: ${GENERATED_DIRECTORY}/${actualName}`,
      );
    }
  }
  for (const name of GENERATED_FILES) {
    let actual: string | undefined;
    try {
      actual = await fs.readFile(path.join(generatedRoot, name), "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
        throw error;
      }
    }
    if (actual !== expected[name]) {
      diagnostics.push(
        `${GENERATED_DIRECTORY}/${name} differs from deterministic projection`,
      );
    }
  }
  return { diagnostics, ok: diagnostics.length === 0 };
}

export async function writeTokenProjection(
  packageRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
  ),
): Promise<void> {
  const outputs = await projectTokenOutputs(packageRoot);
  const generatedRoot = path.join(packageRoot, GENERATED_DIRECTORY);
  await fs.mkdir(generatedRoot, { recursive: true });
  await Promise.all(
    Object.entries(outputs).map(([name, contents]) =>
      fs.writeFile(path.join(generatedRoot, name), contents),
    ),
  );
}

const isCommand =
  process.argv[1] !== undefined &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isCommand) {
  const packageRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
  );
  if (process.argv.includes("--write")) {
    await writeTokenProjection(packageRoot);
    console.log("Atlas token projection generated.");
  } else {
    const result = await checkTokenProjection(packageRoot);
    if (!result.ok) {
      console.error(result.diagnostics.join("\n"));
      process.exitCode = 1;
    } else {
      console.log("Atlas token projection: PASS");
    }
  }
}
