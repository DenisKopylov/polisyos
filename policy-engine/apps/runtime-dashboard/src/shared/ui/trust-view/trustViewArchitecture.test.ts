import fs from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";
import { describe, expect, it } from "vitest";

const trustViewRoot = path.dirname(fileURLToPath(import.meta.url));
const dashboardSourceRoot = path.resolve(trustViewRoot, "../../..");
const repoRoot = path.resolve(dashboardSourceRoot, "../../..");
const sharedRoot = path.resolve(trustViewRoot, "../..");
const governedFiles = [
  ...sourceFiles(trustViewRoot),
  path.join(sharedRoot, "charts/UncertaintyDisplay.tsx"),
  path.join(sharedRoot, "charts/uncertainty-rendering.ts"),
];
const forbiddenRoots = ["@/app", "@/api", "@/features"];

const C04_MECHANISM_PATHS = [
  "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/index.ts",
  "apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts",
] as const;

const C04_ISSUER_CALLERS = [
  "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
  "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
] as const;

const PRESENTATION_COMPONENTS = {
  DisputeBadge: {
    declaration:
      "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
    expectedConsumers: [
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
    ],
  },
  VerificationStatus: {
    declaration:
      "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
    expectedConsumers: [
      "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
    ],
  },
} as const;

const TRUST_GLYPHS_PATH =
  "apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts";
const TRUST_VIEW_BARREL_PATH =
  "apps/runtime-dashboard/src/shared/ui/trust-view/index.ts";

type PresentationComponent = keyof typeof PRESENTATION_COMPONENTS;

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(resolved);
    }
    return /\.(?:ts|tsx)$/u.test(entry.name) ? [resolved] : [];
  });
}

function productionDashboardSources(): string[] {
  return sourceFiles(dashboardSourceRoot)
    .filter((file) => isProductionDashboardSource(sourcePath(file)))
    .sort();
}

function isProductionDashboardSource(relative: string): boolean {
  return (
    /\.(?:ts|tsx)$/u.test(relative) &&
    !/\.(?:a11y\.)?(?:test|spec)\.[cm]?(?:ts|tsx)$/u.test(relative) &&
    !/\.stories\.[cm]?(?:ts|tsx)$/u.test(relative) &&
    !relative.endsWith(".d.ts") &&
    !(relative.includes("/src/test/") && relative.endsWith(".tsx"))
  );
}

function trackedProductionDashboardSources(): string[] {
  return execFileSync("git", ["ls-files", "--", "apps/runtime-dashboard/src"], {
    cwd: repoRoot,
    encoding: "utf8",
  })
    .split("\n")
    .filter(Boolean)
    .filter(isProductionDashboardSource)
    .sort();
}

function sourcePath(file: string): string {
  return path.relative(repoRoot, file).split(path.sep).join("/");
}

function sourceFile(file: string): ts.SourceFile {
  return ts.createSourceFile(
    file,
    fs.readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
}

function resolveModule(importer: string, specifier: string): string | null {
  const unresolved = specifier.startsWith("@/")
    ? path.join(dashboardSourceRoot, specifier.slice(2))
    : specifier.startsWith(".")
      ? path.resolve(path.dirname(importer), specifier)
      : null;
  if (!unresolved) {
    return null;
  }
  const candidates = [
    unresolved,
    `${unresolved}.ts`,
    `${unresolved}.tsx`,
    path.join(unresolved, "index.ts"),
    path.join(unresolved, "index.tsx"),
  ];
  return (
    candidates.find(
      (candidate) =>
        fs.existsSync(candidate) && fs.statSync(candidate).isFile(),
    ) ?? null
  );
}

function namedImportsByTarget(
  ast: ts.SourceFile,
  file: string,
  targets: ReadonlySet<string>,
): Map<string, string> {
  const imports = new Map<string, string>();
  for (const statement of ast.statements) {
    if (
      !ts.isImportDeclaration(statement) ||
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      !statement.importClause?.namedBindings ||
      !ts.isNamedImports(statement.importClause.namedBindings)
    ) {
      continue;
    }
    const resolved = resolveModule(file, statement.moduleSpecifier.text);
    if (!resolved || !targets.has(sourcePath(resolved))) {
      continue;
    }
    for (const element of statement.importClause.namedBindings.elements) {
      imports.set(
        element.name.text,
        element.propertyName?.text ?? element.name.text,
      );
    }
  }
  return imports;
}

function jsxAttributeNames(node: ts.JsxAttributes): string[] {
  return node.properties.flatMap((property) =>
    ts.isJsxAttribute(property) && ts.isIdentifier(property.name)
      ? [property.name.text]
      : [],
  );
}

function componentUses(
  ast: ts.SourceFile,
  imports: Map<string, string>,
): Array<{ component: PresentationComponent; attributes: string[] }> {
  const uses: Array<{
    component: PresentationComponent;
    attributes: string[];
  }> = [];
  const visit = (node: ts.Node) => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tagName = ts.isIdentifier(node.tagName) ? node.tagName.text : null;
      const imported = tagName ? imports.get(tagName) : undefined;
      if (imported === "DisputeBadge" || imported === "VerificationStatus") {
        uses.push({
          component: imported,
          attributes: jsxAttributeNames(node.attributes),
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(ast);
  return uses;
}

function propertyNamesInPropsType(
  ast: ts.SourceFile,
  typeName: string,
): string[] {
  const properties: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node)) &&
      node.name.text === typeName
    ) {
      const members = ts.isTypeAliasDeclaration(node)
        ? ts.isTypeLiteralNode(node.type)
          ? node.type.members
          : []
        : node.members;
      for (const member of members) {
        if (ts.isPropertySignature(member) && member.name) {
          const name =
            ts.isIdentifier(member.name) || ts.isStringLiteral(member.name)
              ? member.name.text
              : null;
          if (name) {
            properties.push(name);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(ast);
  return properties.sort();
}

function presentationPropTypeText(
  ast: ts.SourceFile,
  typeName: string,
): string | null {
  let result: string | null = null;
  const visit = (node: ts.Node) => {
    if (
      (ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node)) &&
      node.name.text === typeName
    ) {
      const members = ts.isTypeAliasDeclaration(node)
        ? ts.isTypeLiteralNode(node.type)
          ? node.type.members
          : []
        : node.members;
      for (const member of members) {
        if (
          ts.isPropertySignature(member) &&
          member.name &&
          (ts.isIdentifier(member.name) || ts.isStringLiteral(member.name)) &&
          member.name.text === "presentation"
        ) {
          result = member.type?.getText(ast) ?? null;
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(ast);
  return result;
}

type IssuerAccessKind =
  | "alias"
  | "default_import"
  | "dynamic_import"
  | "import_equals"
  | "named_import"
  | "namespace_import"
  | "reexport"
  | "require"
  | "side_effect_import"
  | "value_reference";

function unwrapIssuerExpression(expression: ts.Expression): ts.Expression {
  let current = expression;
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isTypeAssertionExpression(current) ||
    ts.isNonNullExpression(current) ||
    ts.isSatisfiesExpression(current) ||
    ts.isPartiallyEmittedExpression(current)
  ) {
    current = current.expression;
  }
  return current;
}

function issuerCalls(
  file: string,
  ast: ts.SourceFile,
): { directCalls: number; unsafeAccesses: IssuerAccessKind[] } {
  const directIssuerNames = new Set<string>();
  const namespaceNames = new Set<string>();
  const unsafeAccesses: IssuerAccessKind[] = [];
  const allowedCaller = (C04_ISSUER_CALLERS as readonly string[]).includes(
    sourcePath(file),
  );

  const targetsIssuer = (specifier: ts.Expression | undefined) => {
    if (!specifier || !ts.isStringLiteralLike(specifier)) return false;
    const resolved = resolveModule(file, specifier.text);
    return Boolean(resolved && sourcePath(resolved) === TRUST_GLYPHS_PATH);
  };

  for (const statement of ast.statements) {
    if (
      ts.isImportDeclaration(statement) &&
      targetsIssuer(statement.moduleSpecifier)
    ) {
      const clause = statement.importClause;
      if (!clause) {
        unsafeAccesses.push("side_effect_import");
        continue;
      }
      if (clause.isTypeOnly) continue;
      if (clause.name) unsafeAccesses.push("default_import");
      const bindings = clause.namedBindings;
      if (bindings && ts.isNamespaceImport(bindings)) {
        namespaceNames.add(bindings.name.text);
        unsafeAccesses.push("namespace_import");
      } else if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          if (element.isTypeOnly) continue;
          const imported = element.propertyName?.text ?? element.name.text;
          if (imported !== "issueTrustPresentation") continue;
          directIssuerNames.add(element.name.text);
          if (element.name.text !== "issueTrustPresentation") {
            unsafeAccesses.push("alias");
          } else if (!allowedCaller) {
            unsafeAccesses.push("named_import");
          }
        }
      }
    }
    if (
      ts.isExportDeclaration(statement) &&
      targetsIssuer(statement.moduleSpecifier) &&
      !statement.isTypeOnly &&
      (!statement.exportClause ||
        ts.isNamespaceExport(statement.exportClause) ||
        (ts.isNamedExports(statement.exportClause) &&
          statement.exportClause.elements.some(
            (element) =>
              !element.isTypeOnly &&
              ["default", "issueTrustPresentation"].includes(
                element.propertyName?.text ?? element.name.text,
              ),
          )))
    ) {
      unsafeAccesses.push("reexport");
    }
    if (
      ts.isImportEqualsDeclaration(statement) &&
      !statement.isTypeOnly &&
      ts.isExternalModuleReference(statement.moduleReference) &&
      targetsIssuer(statement.moduleReference.expression)
    ) {
      unsafeAccesses.push("import_equals");
    }
  }

  const isIssuerExpression = (expression: ts.Expression): boolean => {
    const candidate = unwrapIssuerExpression(expression);
    if (ts.isIdentifier(candidate)) {
      return directIssuerNames.has(candidate.text);
    }
    if (
      ts.isPropertyAccessExpression(candidate) &&
      ts.isIdentifier(candidate.expression)
    ) {
      return (
        namespaceNames.has(candidate.expression.text) &&
        candidate.name.text === "issueTrustPresentation"
      );
    }
    return (
      ts.isElementAccessExpression(candidate) &&
      ts.isIdentifier(candidate.expression) &&
      namespaceNames.has(candidate.expression.text) &&
      ts.isStringLiteralLike(candidate.argumentExpression) &&
      candidate.argumentExpression.text === "issueTrustPresentation"
    );
  };

  const transparentRoot = (expression: ts.Expression): ts.Expression => {
    let current = expression;
    while (
      current.parent &&
      (ts.isParenthesizedExpression(current.parent) ||
        ts.isAsExpression(current.parent) ||
        ts.isTypeAssertionExpression(current.parent) ||
        ts.isNonNullExpression(current.parent) ||
        ts.isSatisfiesExpression(current.parent) ||
        ts.isPartiallyEmittedExpression(current.parent)) &&
      current.parent.expression === current
    ) {
      current = current.parent;
    }
    return current;
  };

  const isIssuerReference = (node: ts.Node): node is ts.Expression => {
    if (ts.isIdentifier(node)) {
      if (
        ts.isImportSpecifier(node.parent) ||
        ts.isNamespaceImport(node.parent)
      ) {
        return false;
      }
      if (
        ts.isExportSpecifier(node.parent) &&
        (node.parent.isTypeOnly ||
          (ts.isNamedExports(node.parent.parent) &&
            ts.isExportDeclaration(node.parent.parent.parent) &&
            node.parent.parent.parent.isTypeOnly))
      ) {
        return false;
      }
      if (
        (ts.isPropertyAccessExpression(node.parent) &&
          node.parent.name === node) ||
        (ts.isElementAccessExpression(node.parent) &&
          node.parent.argumentExpression === node)
      ) {
        return false;
      }
      return directIssuerNames.has(node.text);
    }
    return (
      (ts.isPropertyAccessExpression(node) ||
        ts.isElementAccessExpression(node)) &&
      isIssuerExpression(node)
    );
  };

  let directCalls = 0;
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node) && isIssuerExpression(node.expression)) {
      directCalls += 1;
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      targetsIssuer(node.arguments[0])
    ) {
      unsafeAccesses.push("dynamic_import");
    }
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "require" &&
      targetsIssuer(node.arguments[0])
    ) {
      unsafeAccesses.push("require");
    }
    if (
      ts.isVariableDeclaration(node) &&
      ts.isObjectBindingPattern(node.name) &&
      node.initializer &&
      ts.isIdentifier(node.initializer) &&
      namespaceNames.has(node.initializer.text) &&
      node.name.elements.some(
        (element) =>
          (element.propertyName &&
            ts.isIdentifier(element.propertyName) &&
            element.propertyName.text === "issueTrustPresentation") ||
          (ts.isIdentifier(element.name) &&
            element.name.text === "issueTrustPresentation"),
      )
    ) {
      unsafeAccesses.push("alias");
    }
    if (isIssuerReference(node)) {
      const outer = transparentRoot(node);
      if (
        !(
          ts.isCallExpression(outer.parent) &&
          outer.parent.expression === outer &&
          isIssuerExpression(outer.parent.expression)
        )
      ) {
        unsafeAccesses.push("value_reference");
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(ast);
  return {
    directCalls,
    unsafeAccesses: unsafeAccesses.sort(),
  };
}

function forbiddenImports(file: string): string[] {
  const ast = sourceFile(file);
  const violations: string[] = [];

  function record(specifier: string, position: number) {
    if (!forbiddenRoots.some((root) => specifier.startsWith(root))) {
      return;
    }
    const line = ast.getLineAndCharacterOfPosition(position).line + 1;
    violations.push(`${path.basename(file)}:${line} -> ${specifier}`);
  }

  function visit(node: ts.Node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      record(node.moduleSpecifier.text, node.moduleSpecifier.getStart(ast));
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      record(node.arguments[0].text, node.arguments[0].getStart(ast));
    }
    ts.forEachChild(node, visit);
  }

  visit(ast);
  return violations;
}

describe("shared Trust View architecture", () => {
  it("rejects app API and feature imports from Trust View and its shared consumers", () => {
    expect(governedFiles.flatMap(forbiddenImports)).toEqual([]);
  });

  it.each([
    [
      "namespace property call",
      'import * as trust from "./trust-glyphs"; trust.issueTrustPresentation(null);',
      "namespace_import",
      1,
    ],
    [
      "re-export",
      'export { issueTrustPresentation } from "./trust-glyphs";',
      "reexport",
      0,
    ],
    [
      "dynamic import",
      'void import("./trust-glyphs").then((trust) => trust.issueTrustPresentation(null));',
      "dynamic_import",
      0,
    ],
    [
      "require",
      'const trust = require("./trust-glyphs"); trust.issueTrustPresentation(null);',
      "require",
      0,
    ],
    [
      "local alias",
      'import { issueTrustPresentation } from "./trust-glyphs"; const alias = issueTrustPresentation; alias(null);',
      "value_reference",
      0,
    ],
    [
      "destructuring alias",
      'import * as trust from "./trust-glyphs"; const { issueTrustPresentation: alias } = trust; alias(null);',
      "alias",
      0,
    ],
  ])(
    "rejects %s access to the private issuer",
    (_label, source, kind, calls) => {
      const file = path.join(repoRoot, C04_ISSUER_CALLERS[1]);
      const ast = ts.createSourceFile(
        file,
        source,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TS,
      );

      expect(issuerCalls(file, ast)).toEqual({
        directCalls: calls,
        unsafeAccesses:
          kind === "alias" ? ["alias", "namespace_import"] : [kind],
      });
    },
  );

  it.each([
    [
      "namespace re-export",
      'export * as trustIssuer from "./trust-glyphs";',
      ["reexport"],
    ],
    ["bare star re-export", 'export * from "./trust-glyphs";', ["reexport"]],
    [
      "named alias re-export",
      'export { issueTrustPresentation as trustIssuer } from "./trust-glyphs";',
      ["reexport"],
    ],
    [
      "default re-export",
      'export { default as trustIssuer } from "./trust-glyphs";',
      ["reexport"],
    ],
    [
      "namespace import",
      'import * as trustIssuer from "./trust-glyphs";',
      ["namespace_import"],
    ],
    [
      "default import",
      'import trustIssuer from "./trust-glyphs";',
      ["default_import"],
    ],
    [
      "unauthorized exact named import",
      'import { issueTrustPresentation } from "./trust-glyphs";',
      ["named_import"],
    ],
    [
      "named issuer alias import",
      'import { issueTrustPresentation as trustIssuer } from "./trust-glyphs";',
      ["alias"],
    ],
    ["side-effect import", 'import "./trust-glyphs";', ["side_effect_import"]],
    [
      "import-equals require",
      'import trustIssuer = require("./trust-glyphs");',
      ["import_equals"],
    ],
    ["dynamic import", 'void import("./trust-glyphs");', ["dynamic_import"]],
    ["require", 'void require("./trust-glyphs");', ["require"]],
  ])("rejects runtime-value %s", (_label, source, unsafeAccesses) => {
    const file = path.join(trustViewRoot, "index.ts");
    const ast = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 0,
      unsafeAccesses,
    });
  });

  it.each([
    ['import type TrustDefault from "./trust-glyphs";'],
    ['import type { TrustPresentation } from "./trust-glyphs";'],
    ['import type * as TrustTypes from "./trust-glyphs";'],
    ['import { type TrustPresentation } from "./trust-glyphs";'],
    ['export type * from "./trust-glyphs";'],
    ['export type * as TrustTypes from "./trust-glyphs";'],
    ['export type { TrustPresentation } from "./trust-glyphs";'],
    ['export { type TrustPresentation } from "./trust-glyphs";'],
    ['import type TrustTypes = require("./trust-glyphs");'],
  ])("admits an erased type-only module form", (source) => {
    const file = path.join(trustViewRoot, "index.ts");
    const ast = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 0,
      unsafeAccesses: [],
    });
  });

  it.each([
    ['import { presentTrustPresentation } from "./trust-glyphs";'],
    ['export { truncateHash as hashLabel } from "./trust-glyphs";'],
  ])("admits a named non-issuer module value", (source) => {
    const file = path.join(trustViewRoot, "index.ts");
    const ast = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 0,
      unsafeAccesses: [],
    });
  });

  it.each([
    [
      "runtime local export",
      "export { issueTrustPresentation as trustIssuer };",
      ["value_reference"],
    ],
    [
      "declaration-level type-only local export",
      "export type { issueTrustPresentation };",
      [],
    ],
    [
      "specifier-level type-only local export",
      "export { type issueTrustPresentation };",
      [],
    ],
  ])(
    "classifies %s by emitted value semantics",
    (_label, exportSource, unsafeAccesses) => {
      const file = path.join(repoRoot, C04_ISSUER_CALLERS[1]);
      const ast = ts.createSourceFile(
        file,
        `import { issueTrustPresentation } from "./trust-glyphs"; ${exportSource}`,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TS,
      );

      expect(issuerCalls(file, ast)).toEqual({
        directCalls: 0,
        unsafeAccesses,
      });
    },
  );

  it("counts a transparently wrapped issuer callee as a direct call", () => {
    const file = path.join(repoRoot, C04_ISSUER_CALLERS[1]);
    const ast = ts.createSourceFile(
      file,
      'import { issueTrustPresentation } from "./trust-glyphs"; (issueTrustPresentation)(null);',
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 1,
      unsafeAccesses: [],
    });
  });

  it.each([
    ["comma callee", "(0, issueTrustPresentation)(null);"],
    ["call method", "issueTrustPresentation.call(null, null);"],
    ["Reflect.apply", "Reflect.apply(issueTrustPresentation, null, [null]);"],
    ["callback", "Promise.resolve(null).then(issueTrustPresentation);"],
    ["storage", "const stored = [issueTrustPresentation]; void stored;"],
  ])("rejects an issuer %s value reference", (_label, expression) => {
    const file = path.join(repoRoot, C04_ISSUER_CALLERS[1]);
    const ast = ts.createSourceFile(
      file,
      `import { issueTrustPresentation } from "./trust-glyphs"; ${expression}`,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 0,
      unsafeAccesses: ["value_reference"],
    });
  });

  it("censuses every production consumer over the fixed 625-file C04 denominator", () => {
    const sources = productionDashboardSources();
    expect(sources.map(sourcePath)).toEqual(
      trackedProductionDashboardSources(),
    );
    expect({
      all: sources.length,
      ts: sources.filter((source) => source.endsWith(".ts")).length,
      tsx: sources.filter((source) => source.endsWith(".tsx")).length,
    }).toEqual({ all: 625, ts: 304, tsx: 321 });

    const componentTargets = new Set([
      PRESENTATION_COMPONENTS.DisputeBadge.declaration,
      PRESENTATION_COMPONENTS.VerificationStatus.declaration,
      TRUST_VIEW_BARREL_PATH,
    ]);
    const consumers = new Map<PresentationComponent, string[]>([
      ["DisputeBadge", []],
      ["VerificationStatus", []],
    ]);
    const issuerOwners: string[] = [];
    for (const source of sources) {
      const ast = sourceFile(source);
      const imports = namedImportsByTarget(ast, source, componentTargets);
      for (const use of componentUses(ast, imports)) {
        expect(use.attributes).toContain("presentation");
        expect(use.attributes).not.toEqual(
          expect.arrayContaining(["status", "tone", "metadata"]),
        );
        consumers.get(use.component)?.push(sourcePath(source));
      }
      const issuer = issuerCalls(source, ast);
      expect(issuer.unsafeAccesses).toEqual([]);
      if (issuer.directCalls > 0) {
        issuerOwners.push(sourcePath(source));
        expect(issuer.directCalls).toBe(1);
      }
    }

    for (const [component, expected] of Object.entries(
      PRESENTATION_COMPONENTS,
    ) as Array<
      [
        PresentationComponent,
        (typeof PRESENTATION_COMPONENTS)[PresentationComponent],
      ]
    >) {
      expect(consumers.get(component)?.sort()).toEqual(
        [...expected.expectedConsumers].sort(),
      );
    }
    expect(issuerOwners.sort()).toEqual([...C04_ISSUER_CALLERS].sort());

    const observedMechanisms = new Set<string>([
      TRUST_GLYPHS_PATH,
      TRUST_VIEW_BARREL_PATH,
      ...Object.values(PRESENTATION_COMPONENTS).map(
        ({ declaration }) => declaration,
      ),
      ...issuerOwners,
      ...[...consumers.values()].flat(),
    ]);
    expect([...observedMechanisms].sort()).toEqual(
      [...C04_MECHANISM_PATHS].sort(),
    );
  });

  it("admits only issued presentation props and keeps the issuer private to the barrel", () => {
    for (const [component, detail] of Object.entries(
      PRESENTATION_COMPONENTS,
    ) as Array<
      [
        PresentationComponent,
        (typeof PRESENTATION_COMPONENTS)[PresentationComponent],
      ]
    >) {
      const ast = sourceFile(path.join(repoRoot, detail.declaration));
      const propsType = `${component}Props`;
      expect(propertyNamesInPropsType(ast, propsType)).toEqual(
        component === "DisputeBadge"
          ? ["className", "presentation"]
          : ["className", "presentation", "showLabel"],
      );
      expect(presentationPropTypeText(ast, propsType)).toBe(
        "TrustPresentation",
      );
    }

    const barrel = sourceFile(path.join(repoRoot, TRUST_VIEW_BARREL_PATH));
    const barrelText = barrel.getFullText();
    for (const privateExport of [
      "issueTrustPresentation",
      "isIssuedTrustPresentation",
      "presentTrustPresentation",
      "TrustPresentation",
      "TrustPresentationData",
    ]) {
      expect(barrelText).not.toContain(privateExport);
    }
  });
});
