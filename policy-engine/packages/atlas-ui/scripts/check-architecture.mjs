import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const packageRoot = path.resolve(import.meta.dirname, "..");
const sourceRoot = path.join(packageRoot, "src");
const forbiddenImport =
  /(^@\/|runtime-dashboard|runtime-api-client|(^|\/)apps\/|(^|\/)api(\/|$)|polisyos\/|backend|atlas-v15)/;
const generatedTypeBridges = [
  {
    file: path.join(sourceRoot, "primitives/evidenceTypes.ts"),
    names: new Set([
      "AvailableGovernedProjectionPacket",
      "LegacyProvingGroundPayload",
    ]),
    specifier: "@polisyos/runtime-api-client",
  },
  {
    file: path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
    names: new Set([
      "OperatorDiagnostic",
      "OperatorProjectionStateLabel",
      "RunOperatorDiagnostic",
      "RunOperatorProjectionStateLabel",
    ]),
    specifier: "@polisyos/runtime-api-client",
  },
];

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(resolved);
    return /\.tsx?$/.test(entry.name) ? [resolved] : [];
  });
}

function importedDependencies(file, text = fs.readFileSync(file, "utf8")) {
  const source = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const dependencies = [];
  const visit = (node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      dependencies.push({
        kind: ts.isImportDeclaration(node) ? "import" : "export",
        names:
          ts.isImportDeclaration(node) &&
          node.importClause?.namedBindings &&
          ts.isNamedImports(node.importClause.namedBindings)
            ? node.importClause.namedBindings.elements.map((element) => ({
                imported: element.propertyName?.text ?? element.name.text,
                local: element.name.text,
              }))
            : [],
        specifier: node.moduleSpecifier.text,
        typeOnly:
          ts.isImportDeclaration(node) &&
          node.importClause?.isTypeOnly === true,
      });
    }
    if (
      ts.isImportTypeNode(node) &&
      ts.isLiteralTypeNode(node.argument) &&
      ts.isStringLiteral(node.argument.literal)
    ) {
      dependencies.push({
        kind: "import-type",
        names: [],
        specifier: node.argument.literal.text,
        typeOnly: true,
      });
    }
    if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference) &&
      node.moduleReference.expression &&
      ts.isStringLiteral(node.moduleReference.expression)
    ) {
      dependencies.push({
        kind: "import-equals",
        names: [],
        specifier: node.moduleReference.expression.text,
        typeOnly: node.isTypeOnly,
      });
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      dependencies.push({
        kind: "dynamic",
        names: [],
        specifier: node.arguments[0].text,
        typeOnly: false,
      });
    }
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "require" &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      dependencies.push({
        kind: "require",
        names: [],
        specifier: node.arguments[0].text,
        typeOnly: false,
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return dependencies;
}

function isGeneratedTypeBridge(file, dependency) {
  const bridge = generatedTypeBridges.find(
    (candidate) => candidate.file === file,
  );
  return (
    bridge !== undefined &&
    dependency.kind === "import" &&
    dependency.specifier === bridge.specifier &&
    dependency.typeOnly &&
    dependency.names.length === bridge.names.size &&
    dependency.names.every(
      (name) => name.imported === name.local && bridge.names.has(name.imported),
    )
  );
}

const violations = [];
const evidenceTypeBridge = generatedTypeBridges[0];

const valueImportProbe = importedDependencies(
  evidenceTypeBridge.file,
  'import { AvailableGovernedProjectionPacket, LegacyProvingGroundPayload } from "@polisyos/runtime-api-client";',
)[0];
if (
  !valueImportProbe ||
  isGeneratedTypeBridge(evidenceTypeBridge.file, valueImportProbe)
) {
  violations.push("generated bridge corruption probe accepted a value import");
}

const broadTypeImportProbe = importedDependencies(
  evidenceTypeBridge.file,
  'import type { AvailableGovernedProjectionPacket, LegacyProvingGroundPayload, OperatorDiagnostic } from "@polisyos/runtime-api-client";',
)[0];
if (
  !broadTypeImportProbe ||
  isGeneratedTypeBridge(evidenceTypeBridge.file, broadTypeImportProbe)
) {
  violations.push(
    "generated bridge corruption probe accepted a broad type import",
  );
}

const aliasedTypeImportProbe = importedDependencies(
  evidenceTypeBridge.file,
  'import type { AvailableGovernedProjectionPacket, LegacyProvingGroundPayload as FixturePayload } from "@polisyos/runtime-api-client";',
)[0];
if (
  !aliasedTypeImportProbe ||
  isGeneratedTypeBridge(evidenceTypeBridge.file, aliasedTypeImportProbe)
) {
  violations.push(
    "generated bridge corruption probe accepted an aliased type import",
  );
}

const importTypeProbe = importedDependencies(
  path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
  'type Forbidden = import("@polisyos/runtime-api-client").OperatorDiagnostic;',
)[0];
if (
  !importTypeProbe ||
  !forbiddenImport.test(importTypeProbe.specifier) ||
  isGeneratedTypeBridge(
    path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
    importTypeProbe,
  )
) {
  violations.push("architecture corruption probe missed an import type");
}

const wrongFileProbe = importedDependencies(
  path.join(sourceRoot, "primitives/EvidenceLink.tsx"),
  'import type { AvailableGovernedProjectionPacket, LegacyProvingGroundPayload } from "@polisyos/runtime-api-client";',
)[0];
if (
  !wrongFileProbe ||
  isGeneratedTypeBridge(
    path.join(sourceRoot, "primitives/EvidenceLink.tsx"),
    wrongFileProbe,
  )
) {
  violations.push("generated bridge corruption probe accepted the wrong file");
}

const requireProbe = importedDependencies(
  path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
  'const forbidden = require("@polisyos/runtime-api-client");',
)[0];
if (
  !requireProbe ||
  requireProbe.kind !== "require" ||
  !forbiddenImport.test(requireProbe.specifier) ||
  isGeneratedTypeBridge(
    path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
    requireProbe,
  )
) {
  violations.push("architecture corruption probe missed require()");
}

const importEqualsProbe = importedDependencies(
  path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
  'import Forbidden = require("@polisyos/runtime-api-client");',
)[0];
if (
  !importEqualsProbe ||
  importEqualsProbe.kind !== "import-equals" ||
  !forbiddenImport.test(importEqualsProbe.specifier) ||
  isGeneratedTypeBridge(
    path.join(sourceRoot, "primitives/AuthorityBadge.tsx"),
    importEqualsProbe,
  )
) {
  violations.push("architecture corruption probe missed import-equals");
}

for (const file of walk(sourceRoot)) {
  for (const dependency of importedDependencies(file)) {
    const { specifier } = dependency;
    if (isGeneratedTypeBridge(file, dependency)) {
      continue;
    }
    if (forbiddenImport.test(specifier)) {
      violations.push(`${path.relative(packageRoot, file)} -> ${specifier}`);
    }
    if (specifier.startsWith(".")) {
      const resolved = path.resolve(path.dirname(file), specifier);
      if (!resolved.startsWith(`${packageRoot}${path.sep}`)) {
        violations.push(
          `${path.relative(packageRoot, file)} escapes package -> ${specifier}`,
        );
      }
    }
  }
}

const packageJson = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"),
);
const exportKeys = Object.keys(packageJson.exports ?? {});
if (exportKeys.length !== 1 || exportKeys[0] !== ".") {
  violations.push(
    `package exports must be root-only; received ${exportKeys.join(", ")}`,
  );
}
const rootExport = packageJson.exports?.["."];
if (
  rootExport?.types !== "./src/index.ts" ||
  rootExport?.import !== "./src/index.ts"
) {
  violations.push("root export must resolve types/import to ./src/index.ts");
}

if (violations.length > 0) {
  console.error(violations.join("\n"));
  process.exitCode = 1;
} else {
  console.log(
    `atlas-ui architecture: PASS (${walk(sourceRoot).length} source files)`,
  );
}
