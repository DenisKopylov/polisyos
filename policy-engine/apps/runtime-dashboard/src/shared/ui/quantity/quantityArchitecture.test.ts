import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";
import { describe, expect, it } from "vitest";

const quantityRoot = path.dirname(fileURLToPath(import.meta.url));
const forbiddenRoots = ["@/app", "@/api", "@/features"];

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(resolved);
    }
    return /\.(?:ts|tsx)$/u.test(entry.name) ? [resolved] : [];
  });
}

function forbiddenImports(file: string): string[] {
  const source = fs.readFileSync(file, "utf8");
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const violations: string[] = [];

  function record(specifier: string, position: number) {
    if (!forbiddenRoots.some((root) => specifier.startsWith(root))) {
      return;
    }
    const line = ast.getLineAndCharacterOfPosition(position).line + 1;
    violations.push(
      `${path.relative(quantityRoot, file)}:${line} -> ${specifier}`,
    );
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

describe("shared quantity architecture", () => {
  it("rejects app API and feature imports from the shared quantity family", () => {
    const violations = sourceFiles(quantityRoot).flatMap(forbiddenImports);
    expect(violations).toEqual([]);
  });
});
