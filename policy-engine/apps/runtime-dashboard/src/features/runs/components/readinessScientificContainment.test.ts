import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

type SourceUnit = { file: string; text: string };
type ParsedUnit = SourceUnit & { source: ts.SourceFile };
type SourceOverrides = Record<string, string>;

const dashboardRoot = path.resolve(import.meta.dirname, "../../../..");
const sourceRoot = path.join(dashboardRoot, "src");
const readinessPanel = path.join(
  sourceRoot,
  "features/runs/components/PublicSectorReadinessPanel.tsx",
);
const scientificPanel = path.join(
  sourceRoot,
  "features/runs/components/ScientificDepthPanel.tsx",
);
const runDetailLayout = path.join(
  sourceRoot,
  "features/runs/routes/RunDetailLayout.tsx",
);
const governanceTab = path.join(
  sourceRoot,
  "features/runs/routes/tabs/GovernanceTab.tsx",
);
const siblingWrapper = path.join(
  sourceRoot,
  "features/runs/components/ReadinessSiblingWrapper.tsx",
);
const retiredModules = [
  path.join(sourceRoot, "features/runs/domain/publicSectorReadiness.ts"),
  path.join(sourceRoot, "features/runs/domain/scientificDepth.ts"),
];
const panelNames = new Set(["PublicSectorReadinessPanel", "ScientificDepthPanel"]);
const sourceExtensions = [".tsx", ".ts", "/index.tsx", "/index.ts"];

function productionSources(root: string, overrides: SourceOverrides): SourceUnit[] {
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(root, entry.name);
    if (entry.isDirectory()) return productionSources(file, overrides);
    if (
      !entry.isFile() ||
      ![".ts", ".tsx"].includes(path.extname(file)) ||
      /\.(test|a11y\.test)\.[tj]sx?$/.test(file)
    ) {
      return [];
    }
    return [{ file, text: overrides[file] ?? fs.readFileSync(file, "utf8") }];
  });
}

function parse(unit: SourceUnit) {
  return ts.createSourceFile(
    unit.file,
    unit.text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
}

function resolveImport(
  file: string,
  specifier: string,
  knownFiles: ReadonlySet<string>,
): string | null {
  const root = specifier.startsWith("@/")
    ? path.join(sourceRoot, specifier.slice(2))
    : specifier.startsWith(".")
      ? path.resolve(path.dirname(file), specifier)
      : null;
  if (!root) return null;
  for (const suffix of sourceExtensions) {
    const candidate = `${root}${suffix}`;
    if (
      knownFiles.has(candidate) ||
      fs.existsSync(candidate) ||
      retiredModules.includes(candidate)
    ) {
      return candidate;
    }
  }
  return null;
}

function importEdgesFromSource(
  file: string,
  source: ts.SourceFile,
  knownFiles: ReadonlySet<string>,
): Array<{ specifier: string; target: string | null }> {
  const edges: Array<{ specifier: string; target: string | null }> = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      edges.push({
        specifier: node.moduleSpecifier.text,
        target: resolveImport(file, node.moduleSpecifier.text, knownFiles),
      });
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      edges.push({
        specifier: node.arguments[0].text,
        target: resolveImport(file, node.arguments[0].text, knownFiles),
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return edges;
}

function parsedUnit(unit: SourceUnit): ParsedUnit {
  return { ...unit, source: parse(unit) };
}

const baseUnitsByFile = new Map(
  productionSources(sourceRoot, {}).map((unit) => {
    const parsed = parsedUnit(unit);
    return [parsed.file, parsed] as const;
  }),
);
const baseKnownFiles = new Set(baseUnitsByFile.keys());
const baseEdges = [...baseUnitsByFile.values()].flatMap((unit) =>
  importEdgesFromSource(unit.file, unit.source, baseKnownFiles).map((edge) => ({
    ...edge,
    file: unit.file,
  })),
);

function componentDeclaration(source: ts.SourceFile, name: string) {
  return source.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement) && statement.name?.text === name,
  );
}

function jsxTagName(node: ts.JsxOpeningLikeElement) {
  return ts.isIdentifier(node.tagName) ? node.tagName.text : node.tagName.getText();
}

function isSanctionedUnavailableCall(node: ts.Expression): boolean {
  return (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "t" &&
    node.arguments.length === 1 &&
    ts.isStringLiteral(node.arguments[0]) &&
    node.arguments[0].text === "common.unavailable"
  );
}

function isSanctionedI18nBinding(node: ts.CallExpression): boolean {
  const bindingElement =
    ts.isVariableDeclaration(node.parent) &&
    ts.isObjectBindingPattern(node.parent.name) &&
    node.parent.name.elements.length === 1
      ? node.parent.name.elements[0]
      : undefined;
  if (
    !ts.isIdentifier(node.expression) ||
    node.expression.text !== "useI18n" ||
    node.arguments.length !== 0 ||
    !ts.isVariableDeclaration(node.parent) ||
    !ts.isObjectBindingPattern(node.parent.name) ||
    !bindingElement ||
    bindingElement.propertyName !== undefined ||
    !ts.isIdentifier(bindingElement.name) ||
    bindingElement.name.text !== "t" ||
    !ts.isVariableDeclarationList(node.parent.parent) ||
    (node.parent.parent.flags & ts.NodeFlags.Const) === 0
  ) {
    return false;
  }
  return true;
}

function hasExactUnavailableReturn(
  declaration: ts.FunctionDeclaration,
  testId: string,
): boolean {
  const statements = declaration.body?.statements;
  if (!statements || statements.length !== 2) return false;
  const [binding, returnStatement] = statements;
  if (
    !ts.isVariableStatement(binding) ||
    binding.declarationList.declarations.length !== 1 ||
    !ts.isVariableDeclaration(binding.declarationList.declarations[0]) ||
    !binding.declarationList.declarations[0].initializer ||
    !ts.isCallExpression(binding.declarationList.declarations[0].initializer) ||
    !isSanctionedI18nBinding(binding.declarationList.declarations[0].initializer) ||
    !ts.isReturnStatement(returnStatement) ||
    !returnStatement.expression
  ) {
    return false;
  }
  let result = returnStatement.expression;
  while (ts.isParenthesizedExpression(result)) result = result.expression;
  if (!ts.isJsxElement(result) || !ts.isIdentifier(result.openingElement.tagName)) {
    return false;
  }
  if (
    result.openingElement.tagName.text !== "section" ||
    !ts.isIdentifier(result.closingElement.tagName) ||
    result.closingElement.tagName.text !== "section"
  ) {
    return false;
  }
  const attributes = result.openingElement.attributes.properties;
  if (
    attributes.length !== 1 ||
    !ts.isJsxAttribute(attributes[0]) ||
    !ts.isIdentifier(attributes[0].name) ||
    attributes[0].name.text !== "data-testid" ||
    !attributes[0].initializer ||
    !ts.isStringLiteral(attributes[0].initializer) ||
    attributes[0].initializer.text !== testId
  ) {
    return false;
  }
  const meaningfulChildren = result.children.filter(
    (child) => !ts.isJsxText(child) || child.text.trim() !== "",
  );
  return (
    meaningfulChildren.length === 1 &&
    ts.isJsxExpression(meaningfulChildren[0]) &&
    meaningfulChildren[0].expression !== undefined &&
    isSanctionedUnavailableCall(meaningfulChildren[0].expression)
  );
}

function hasSanctionedI18nImport(source: ts.SourceFile): boolean {
  return source.statements.some((statement) => {
    if (
      !ts.isImportDeclaration(statement) ||
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      statement.moduleSpecifier.text !== "@/shared/i18n/LocaleProvider"
    ) {
      return false;
    }
    const namedBindings = statement.importClause?.namedBindings;
    if (!namedBindings || !ts.isNamedImports(namedBindings)) return false;
    return namedBindings.elements.some(
      (element) =>
        element.name.text === "useI18n" && element.propertyName === undefined,
    );
  });
}

function analysis(overrides: SourceOverrides = {}) {
  const byFile = new Map(baseUnitsByFile);
  for (const [file, text] of Object.entries(overrides)) {
    byFile.set(file, parsedUnit({ file, text }));
  }
  const knownFiles = new Set(byFile.keys());
  const errors: string[] = [];
  const edges = [
    ...baseEdges.filter((edge) => !Object.hasOwn(overrides, edge.file)),
    ...Object.keys(overrides).flatMap((file) => {
      const unit = byFile.get(file);
      if (!unit) return [];
      return importEdgesFromSource(file, unit.source, knownFiles).map((edge) => ({
        ...edge,
        file,
      }));
    }),
  ];
  const roots = [runDetailLayout, governanceTab];
  const reachable = new Set<string>();
  const queue = [...roots];
  while (queue.length) {
    const file = queue.shift();
    if (!file || reachable.has(file)) continue;
    reachable.add(file);
    for (const edge of edges.filter((candidate) => candidate.file === file)) {
      if (edge.target && byFile.has(edge.target)) queue.push(edge.target);
    }
  }
  const legacyEdges = edges.filter(
    (edge) => edge.target && retiredModules.includes(edge.target),
  );
  if (legacyEdges.length) {
    errors.push(...legacyEdges.map((edge) => `retired-import:${edge.file}`));
  }
  for (const retired of retiredModules) {
    if (fs.existsSync(retired)) errors.push(`retired-module-survives:${retired}`);
    if (reachable.has(retired)) errors.push(`retired-module-reachable:${retired}`);
  }

  const mounts: Array<{ file: string; name: string; attributes: ts.JsxAttributes }> = [];
  for (const file of reachable) {
    const unit = byFile.get(file);
    if (!unit) continue;
    const visit = (node: ts.Node) => {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const name = jsxTagName(node);
        if (panelNames.has(name)) mounts.push({ file, name, attributes: node.attributes });
      }
      ts.forEachChild(node, visit);
    };
    visit(unit.source);
  }
  const mountCounts = new Map<string, number>();
  for (const mount of mounts) {
    mountCounts.set(mount.name, (mountCounts.get(mount.name) ?? 0) + 1);
    if (mount.attributes.properties.length) errors.push(`panel-mount-props:${mount.file}`);
  }
  if (mounts.length !== 3) errors.push(`mount-count:${mounts.length}`);
  if (mountCounts.get("PublicSectorReadinessPanel") !== 2) errors.push("readiness-mount-count");
  if (mountCounts.get("ScientificDepthPanel") !== 1) errors.push("scientific-mount-count");

  for (const [name, file, testId] of [
    [
      "PublicSectorReadinessPanel",
      readinessPanel,
      "public-sector-readiness-panel",
    ],
    ["ScientificDepthPanel", scientificPanel, "scientific-depth-panel"],
  ] as const) {
    const unit = byFile.get(file);
    if (!unit) {
      errors.push(`panel-missing:${name}`);
      continue;
    }
    const source = unit.source;
    const declaration = componentDeclaration(source, name);
    if (!declaration || declaration.parameters.length) errors.push(`panel-input:${name}`);
    if (!declaration?.body) continue;
    let unavailableCalls = 0;
    let i18nBindings = 0;
    let expressions = 0;
    let text = 0;
    let components = 0;
    let spreads = 0;
    let calls = 0;
    const visit = (node: ts.Node) => {
      if (ts.isJsxExpression(node) && node.expression) {
        if (isSanctionedUnavailableCall(node.expression)) {
          unavailableCalls += 1;
        } else {
          expressions += 1;
        }
      }
      if (ts.isJsxText(node) && node.text.trim() !== "") text += 1;
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        if (/^[A-Z]/.test(jsxTagName(node))) components += 1;
      }
      if (ts.isJsxSpreadAttribute(node)) spreads += 1;
      if (ts.isCallExpression(node)) {
        if (isSanctionedI18nBinding(node)) {
          i18nBindings += 1;
        } else if (
          !(
            isSanctionedUnavailableCall(node) &&
            ts.isJsxExpression(node.parent)
          )
        ) {
          calls += 1;
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(declaration.body);
    if (
      !hasSanctionedI18nImport(source) ||
      !hasExactUnavailableReturn(declaration, testId) ||
      unavailableCalls !== 1 ||
      i18nBindings !== 1 ||
      expressions ||
      text ||
      components ||
      spreads ||
      calls
    ) {
      errors.push(`panel-emission:${name}`);
    }
  }
  return errors;
}

describe("readiness/scientific containment", () => {
  it("derives every production mount and proves constant unavailable emission", () => {
    expect(analysis()).toEqual([]);
  });

  it("rejects direct-helper, alias, arbitrary-key, control-flow, off-JSX call, wrapper, prop-spread, conditional, and sibling-route corruptions", () => {
    const readiness = fs.readFileSync(readinessPanel, "utf8");
    const scientific = fs.readFileSync(scientificPanel, "utf8");
    const layout = fs.readFileSync(runDetailLayout, "utf8");
    const reachableSiblingMount = {
      [runDetailLayout]: layout
        .replace(
          'import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";',
          'import { RunBreadcrumbs } from "@/features/runs/components/RunBreadcrumbs";\nimport { ReadinessSiblingWrapper } from "@/features/runs/components/ReadinessSiblingWrapper";',
        )
        .replace("<ScientificDepthPanel />", "<ReadinessSiblingWrapper />\n                <ScientificDepthPanel />"),
      [siblingWrapper]: `import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";\n\nexport function ReadinessSiblingWrapper() {\n  return <PublicSectorReadinessPanel />;\n}\n`,
    };
    const cases: SourceOverrides[] = [
      {
        [readinessPanel]: readiness.replace(
          "const { t } = useI18n();",
          "const { t } = useI18n();\n  const value = helper();",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          "{ useI18n }",
          "{ useI18n as i18n }",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          "common.unavailable",
          "common.unknown",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          '{t("common.unavailable")}',
          "<Unavailable />",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          '{t("common.unavailable")}',
          '{t("common.unavailable")} approved',
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          "const { t } = useI18n();",
          "const { arbitrary: t } = useI18n();",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          "  return (",
          "  if (window.name) return null;\n\n  return (",
        ),
      },
      {
        [scientificPanel]: scientific.replace(
          "const { t } = useI18n();",
          'const { t } = useI18n();\n  t("common.unavailable");',
        ),
      },
      { [readinessPanel]: readiness.replace("<section", "<section {...props}") },
      {
        [scientificPanel]: scientific.replace(
          '{t("common.unavailable")}',
          '{ready ? t("common.unavailable") : "waiting"}',
        ),
      },
      reachableSiblingMount,
    ];

    for (const corruption of cases) {
      expect(analysis(corruption)).not.toEqual([]);
    }
  });
});
