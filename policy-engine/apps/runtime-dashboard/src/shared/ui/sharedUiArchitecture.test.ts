import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const dashboardRoot = path.resolve(import.meta.dirname, "../../..");
const productRoot = path.resolve(dashboardRoot, "../..");
const packageCompoundsRoot = path.join(
  productRoot,
  "packages/atlas-ui/src/compounds",
);
const packagePatternsRoot = path.join(
  productRoot,
  "packages/atlas-ui/src/patterns",
);
const dashboardSharedRoot = path.join(dashboardRoot, "src/shared");
const dashboardSharedUiRoot = path.join(dashboardSharedRoot, "ui");
const supportedExtensions = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".mjs",
]);
const migratedCompounds = new Set([
  "JsonPreview",
  "VirtualList",
  "VirtualTable",
]);
const migratedPatterns = new Set(["DetailLayout", "FilterPanel"]);

type SourceUnit = {
  file: string;
  text: string;
};

function supportedSources(root: string): SourceUnit[] {
  if (!fs.existsSync(root)) {
    return [];
  }
  return fs
    .readdirSync(root, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const file = path.join(root, entry.name);
      if (entry.isDirectory()) {
        return supportedSources(file);
      }
      if (
        !entry.isFile() ||
        !supportedExtensions.has(path.extname(entry.name))
      ) {
        return [];
      }
      return [{ file, text: fs.readFileSync(file, "utf8") }];
    });
}

function liveCompoundSources(): SourceUnit[] {
  return [dashboardSharedUiRoot, packageCompoundsRoot].flatMap((root) => {
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

function livePatternSources(): SourceUnit[] {
  if (!fs.existsSync(packagePatternsRoot)) {
    return [];
  }
  return fs
    .readdirSync(packagePatternsRoot, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isFile() &&
        entry.name.endsWith(".tsx") &&
        migratedPatterns.has(path.basename(entry.name, ".tsx")),
    )
    .map((entry) => {
      const file = path.join(packagePatternsRoot, entry.name);
      return { file, text: fs.readFileSync(file, "utf8") };
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

function sharedLayerDependencyViolations(units: SourceUnit[]): string[] {
  return units.flatMap((unit) =>
    dependencySpecifiers(unit)
      .filter(
        (specifier) =>
          specifier === "@/app" ||
          specifier.startsWith("@/app/") ||
          specifier === "@/features" ||
          specifier.startsWith("@/features/"),
      )
      .map(
        (specifier) =>
          `${path.relative(productRoot, unit.file)} -> ${specifier}`,
      ),
  );
}

function packagePatternDependencyViolations(units: SourceUnit[]): string[] {
  return appDependencyViolations(
    units.filter((unit) =>
      unit.file.startsWith(`${packagePatternsRoot}${path.sep}`),
    ),
  );
}

describe("shared UI architecture", () => {
  it("rejects every remaining shared to app API or feature edge from the measured manifest", () => {
    const units = supportedSources(dashboardSharedRoot);
    expect(units.length).toBeGreaterThan(0);
    expect(sharedLayerDependencyViolations(units)).toEqual([]);

    const probePath = path.join(
      dashboardSharedRoot,
      "ui/CorruptedSharedBoundary.tsx",
    );
    const corruptions: SourceUnit[] = [
      {
        file: probePath,
        text: 'import { useWorkspace } from "@/app/workspaces";',
      },
      {
        file: probePath,
        text: 'export { useRuns } from "@/features/runs/api/useRuns";',
      },
      {
        file: probePath,
        text: 'const appState = import("@/app/state/usePreferencesStore");',
      },
      {
        file: probePath,
        text: 'import * as RunsApi from "@/features/runs/api/useRunsSample";',
      },
    ];

    expect(sharedLayerDependencyViolations(corruptions)).toEqual([
      "apps/runtime-dashboard/src/shared/ui/CorruptedSharedBoundary.tsx -> @/app/workspaces",
      "apps/runtime-dashboard/src/shared/ui/CorruptedSharedBoundary.tsx -> @/features/runs/api/useRuns",
      "apps/runtime-dashboard/src/shared/ui/CorruptedSharedBoundary.tsx -> @/app/state/usePreferencesStore",
      "apps/runtime-dashboard/src/shared/ui/CorruptedSharedBoundary.tsx -> @/features/runs/api/useRunsSample",
    ]);
  });

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

  it("accepts an app-owned adapter feeding typed pattern presentation props", () => {
    const units = livePatternSources();
    expect(
      new Set(units.map((unit) => path.basename(unit.file, ".tsx"))),
    ).toEqual(migratedPatterns);
    expect(packagePatternDependencyViolations(units)).toEqual([]);

    const appAdapter: SourceUnit = {
      file: path.join(
        dashboardRoot,
        "src/features/runs/routes/PatternPresentationAdapter.tsx",
      ),
      text: [
        'import { useRuns } from "@/api/hooks/useRuns";',
        'import { DetailLayout } from "@polisyos/atlas-ui";',
        'type PresentationProps = React.ComponentProps<typeof DetailLayout>;',
        "export function PatternPresentationAdapter(props: PresentationProps) {",
        "  useRuns();",
        "  return <DetailLayout {...props} />;",
        "}",
      ].join("\n"),
    };
    expect(
      packagePatternDependencyViolations([...units, appAdapter]),
    ).toEqual([]);

    const corruptedPattern = path.join(
      packagePatternsRoot,
      "CorruptedPattern.tsx",
    );
    const corruptions: SourceUnit[] = [
      {
        file: corruptedPattern,
        text: 'import { api } from "@/api/client";',
      },
      {
        file: corruptedPattern,
        text: 'const featureState = import("@/features/runs/state");',
      },
      {
        file: corruptedPattern,
        text: 'export { useWorkspace } from "@/app/workspaces";',
      },
    ];

    expect(packagePatternDependencyViolations(corruptions)).toEqual([
      "packages/atlas-ui/src/patterns/CorruptedPattern.tsx -> @/api/client",
      "packages/atlas-ui/src/patterns/CorruptedPattern.tsx -> @/features/runs/state",
      "packages/atlas-ui/src/patterns/CorruptedPattern.tsx -> @/app/workspaces",
    ]);
  });
});
