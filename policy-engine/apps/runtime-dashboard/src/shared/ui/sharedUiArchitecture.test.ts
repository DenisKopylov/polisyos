import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const dashboardRoot = path.resolve(import.meta.dirname, "../../..");
const productRoot = path.resolve(dashboardRoot, "../..");
const packageCompoundsRoot = path.join(
  productRoot,
  "packages/atlas-ui/src/compounds",
);
const dashboardSharedRoot = path.join(dashboardRoot, "src/shared/ui");
const migratedCompounds = new Set([
  "JsonPreview",
  "VirtualList",
  "VirtualTable",
]);

type SourceUnit = {
  file: string;
  text: string;
};

function liveCompoundSources(): SourceUnit[] {
  return [dashboardSharedRoot, packageCompoundsRoot].flatMap((root) => {
    if (!fs.existsSync(root)) {
      return [];
    }
    return fs
      .readdirSync(root, { withFileTypes: true })
      .filter(
        (entry) =>
          entry.isFile() &&
          entry.name.endsWith(".tsx") &&
          migratedCompounds.has(path.basename(entry.name, ".tsx")),
      )
      .map((entry) => {
        const file = path.join(root, entry.name);
        return { file, text: fs.readFileSync(file, "utf8") };
      });
  });
}

function dependencySpecifiers(unit: SourceUnit): string[] {
  const source = ts.createSourceFile(
    unit.file,
    unit.text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const dependencies: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      dependencies.push(node.moduleSpecifier.text);
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      dependencies.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return dependencies;
}

function appDependencyViolations(units: SourceUnit[]): string[] {
  return units.flatMap((unit) =>
    dependencySpecifiers(unit)
      .filter(
        (specifier) =>
          specifier.startsWith("@/") ||
          specifier.includes("apps/runtime-dashboard"),
      )
      .map(
        (specifier) =>
          `${path.relative(productRoot, unit.file)} -> ${specifier}`,
      ),
  );
}

describe("shared UI architecture", () => {
  it("rejects a compound importing app API or feature state", () => {
    const units = liveCompoundSources();
    expect(
      new Set(units.map((unit) => path.basename(unit.file, ".tsx"))),
    ).toEqual(migratedCompounds);
    expect(appDependencyViolations(units)).toEqual([]);

    const probePath = path.join(packageCompoundsRoot, "CorruptedCompound.tsx");
    const probes = [
      {
        file: probePath,
        text: 'import { api } from "@/api/client";',
      },
      {
        file: probePath,
        text: 'const state = import("@/features/runs/state");',
      },
      {
        file: probePath,
        text: 'export { useWorkspace } from "@/app/workspaces";',
      },
    ];

    expect(appDependencyViolations(probes)).toEqual([
      "packages/atlas-ui/src/compounds/CorruptedCompound.tsx -> @/api/client",
      "packages/atlas-ui/src/compounds/CorruptedCompound.tsx -> @/features/runs/state",
      "packages/atlas-ui/src/compounds/CorruptedCompound.tsx -> @/app/workspaces",
    ]);
  });
});
