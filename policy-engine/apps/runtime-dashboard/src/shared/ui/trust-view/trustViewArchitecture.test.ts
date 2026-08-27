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
  | "dynamic_import"
  | "namespace_property_call"
  | "reexport"
  | "require";

function issuerCalls(
  file: string,
  ast: ts.SourceFile,
): { directCalls: number; unsafeAccesses: IssuerAccessKind[] } {
  const directIssuerNames = new Set<string>();
  const namespaceNames = new Set<string>();
  const unsafeAccesses = new Set<IssuerAccessKind>();

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
      const bindings = statement.importClause?.namedBindings;
      if (bindings && ts.isNamespaceImport(bindings)) {
        namespaceNames.add(bindings.name.text);
      } else if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          const imported = element.propertyName?.text ?? element.name.text;
          if (imported !== "issueTrustPresentation") continue;
          if (element.name.text === "issueTrustPresentation") {
            directIssuerNames.add(element.name.text);
          } else {
            unsafeAccesses.add("alias");
          }
        }
      }
    }
    if (
      ts.isExportDeclaration(statement) &&
      targetsIssuer(statement.moduleSpecifier) &&
      (!statement.exportClause ||
        (ts.isNamedExports(statement.exportClause) &&
          statement.exportClause.elements.some(
            (element) =>
              (element.propertyName?.text ?? element.name.text) ===
              "issueTrustPresentation",
          )))
    ) {
      unsafeAccesses.add("reexport");
    }
  }

  let directCalls = 0;
  const visit = (node: ts.Node) => {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      directIssuerNames.has(node.expression.text)
    ) {
      directCalls += 1;
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      targetsIssuer(node.arguments[0])
    ) {
      unsafeAccesses.add("dynamic_import");
    }
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "require" &&
      targetsIssuer(node.arguments[0])
    ) {
      unsafeAccesses.add("require");
    }
    if (
      ts.isCallExpression(node) &&
      ((ts.isPropertyAccessExpression(node.expression) &&
        ts.isIdentifier(node.expression.expression) &&
        namespaceNames.has(node.expression.expression.text) &&
        node.expression.name.text === "issueTrustPresentation") ||
        (ts.isElementAccessExpression(node.expression) &&
          ts.isIdentifier(node.expression.expression) &&
          namespaceNames.has(node.expression.expression.text) &&
          ts.isStringLiteralLike(node.expression.argumentExpression) &&
          node.expression.argumentExpression.text === "issueTrustPresentation"))
    ) {
      unsafeAccesses.add("namespace_property_call");
    }
    if (
      ts.isVariableDeclaration(node) &&
      node.initializer &&
      ts.isIdentifier(node.initializer) &&
      directIssuerNames.has(node.initializer.text)
    ) {
      unsafeAccesses.add("alias");
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
      unsafeAccesses.add("alias");
    }
    ts.forEachChild(node, visit);
  };
  visit(ast);
  return {
    directCalls,
    unsafeAccesses: [...unsafeAccesses].sort(),
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
      "namespace_property_call",
    ],
    [
      "re-export",
      'export { issueTrustPresentation } from "./trust-glyphs";',
      "reexport",
    ],
    [
      "dynamic import",
      'void import("./trust-glyphs").then((trust) => trust.issueTrustPresentation(null));',
      "dynamic_import",
    ],
    [
      "require",
      'const trust = require("./trust-glyphs"); trust.issueTrustPresentation(null);',
      "require",
    ],
    [
      "local alias",
      'import { issueTrustPresentation } from "./trust-glyphs"; const alias = issueTrustPresentation; alias(null);',
      "alias",
    ],
    [
      "destructuring alias",
      'import * as trust from "./trust-glyphs"; const { issueTrustPresentation: alias } = trust; alias(null);',
      "alias",
    ],
  ])("rejects %s access to the private issuer", (_label, source, kind) => {
    const file = path.join(trustViewRoot, "authority-access-probe.ts");
    const ast = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS,
    );

    expect(issuerCalls(file, ast)).toEqual({
      directCalls: 0,
      unsafeAccesses: [kind],
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
    expect(issuerOwners.sort()).toEqual([
      "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
      "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
    ]);

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
