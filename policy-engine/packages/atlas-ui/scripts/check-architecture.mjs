import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const packageRoot = path.resolve(import.meta.dirname, "..");
const sourceRoot = path.join(packageRoot, "src");
const forbiddenImport =
  /(^@\/|runtime-dashboard|runtime-api-client|(^|\/)apps\/|(^|\/)api(\/|$)|polisyos\/|backend|atlas-v15)/;

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(resolved);
    return /\.tsx?$/.test(entry.name) ? [resolved] : [];
  });
}

function importedSpecifiers(file) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const specifiers = [];
  const visit = (node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specifiers.push(node.moduleSpecifier.text);
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return specifiers;
}

const violations = [];
for (const file of walk(sourceRoot)) {
  for (const specifier of importedSpecifiers(file)) {
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
