import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const packageRoot = path.resolve(import.meta.dirname, "..");
const productRoot = path.resolve(packageRoot, "../..");
const dashboardRoot = path.join(productRoot, "apps/runtime-dashboard");

const FOUNDATION_FAMILIES = {
  AsyncSection: ["AsyncSection"],
  Badge: ["Badge", "badgeVariants"],
  Button: ["Button", "buttonVariants"],
  Card: [
    "Card",
    "CardContent",
    "CardDescription",
    "CardFooter",
    "CardHeader",
    "CardTitle",
  ],
  EmptyState: ["EmptyState"],
  Icon: ["Icon", "Spinner", "iconVariants"],
  Skeleton: [
    "MetricsSkeleton",
    "PageSkeleton",
    "PanelSkeleton",
    "SkeletonBlock",
    "SkeletonCard",
    "SkeletonChart",
    "SkeletonTable",
    "SkeletonText",
  ],
  Text: ["Text", "TextPresentationProvider"],
} as const;

function walkTypeScriptFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) {
    return [];
  }
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return walkTypeScriptFiles(resolved);
    }
    return /\.tsx?$/.test(entry.name) ? [resolved] : [];
  });
}

type SourceUnit = {
  file: string;
  source: ts.SourceFile;
};

function sourceUnit(
  file: string,
  text = fs.readFileSync(file, "utf8"),
): SourceUnit {
  return {
    file,
    source: ts.createSourceFile(
      file,
      text,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    ),
  };
}

function exportedNames(source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  const isExported = (node: ts.Node) =>
    ts.canHaveModifiers(node) &&
    ts
      .getModifiers(node)
      ?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword);

  for (const statement of source.statements) {
    if (
      (ts.isFunctionDeclaration(statement) ||
        ts.isClassDeclaration(statement) ||
        ts.isInterfaceDeclaration(statement) ||
        ts.isTypeAliasDeclaration(statement)) &&
      isExported(statement) &&
      statement.name
    ) {
      names.add(statement.name.text);
    }
    if (ts.isVariableStatement(statement) && isExported(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) {
          names.add(declaration.name.text);
        }
      }
    }
    if (
      ts.isExportDeclaration(statement) &&
      statement.exportClause &&
      ts.isNamedExports(statement.exportClause)
    ) {
      for (const element of statement.exportClause.elements) {
        names.add(element.name.text);
      }
    }
  }
  return names;
}

function packageReexports({ file, source }: SourceUnit): string[] {
  return source.statements.flatMap((statement) => {
    if (
      !ts.isExportDeclaration(statement) ||
      !statement.moduleSpecifier ||
      !ts.isStringLiteral(statement.moduleSpecifier)
    ) {
      return [];
    }

    const specifier = statement.moduleSpecifier.text;
    const resolvedSpecifier = specifier.startsWith(".")
      ? path.resolve(path.dirname(file), specifier)
      : null;
    const resolvesIntoPackage =
      resolvedSpecifier === packageRoot ||
      resolvedSpecifier?.startsWith(`${packageRoot}${path.sep}`) === true;
    return specifier === "@polisyos/atlas-ui" ||
      specifier.startsWith("@polisyos/atlas-ui/") ||
      resolvesIntoPackage
      ? [specifier]
      : [];
  });
}

function foundationOwnershipViolations(units: SourceUnit[]): string[] {
  const violations: string[] = [];

  for (const [family, symbols] of Object.entries(FOUNDATION_FAMILIES)) {
    const owners = units
      .filter(({ source }) => {
        const names = exportedNames(source);
        return symbols.some((symbol) => names.has(symbol));
      })
      .map(({ file }) => path.relative(productRoot, file))
      .sort();
    const expectedOwner = `packages/atlas-ui/src/primitives/${family}.tsx`;
    if (owners.length !== 1 || owners[0] !== expectedOwner) {
      violations.push(`${family}: ${owners.join(", ") || "owner missing"}`);
    }
  }

  for (const unit of units) {
    if (unit.file.startsWith(`${packageRoot}${path.sep}`)) {
      continue;
    }
    for (const specifier of packageReexports(unit)) {
      violations.push(
        `package re-export: ${path.relative(productRoot, unit.file)} -> ${specifier}`,
      );
    }
  }

  return violations;
}

describe("foundation primitive ownership", () => {
  it("rejects a duplicate foundation primitive owner while the old path still exports it", () => {
    const roots = [
      path.join(packageRoot, "src/primitives"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const files = roots.flatMap(walkTypeScriptFiles);
    const violations = foundationOwnershipViolations(
      files.map((file) => sourceUnit(file)),
    );

    const legacyBarrel = path.join(
      dashboardRoot,
      "src/shared/ui/primitives/index.ts",
    );
    const legacyExports: string[] = [];
    if (fs.existsSync(legacyBarrel)) {
      const source = ts.createSourceFile(
        legacyBarrel,
        fs.readFileSync(legacyBarrel, "utf8"),
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TS,
      );
      for (const statement of source.statements) {
        const moduleSpecifier = ts.isExportDeclaration(statement)
          ? statement.moduleSpecifier
          : undefined;
        if (
          moduleSpecifier &&
          ts.isStringLiteral(moduleSpecifier) &&
          Object.keys(FOUNDATION_FAMILIES).some(
            (family) => moduleSpecifier.text === `../${family}`,
          )
        ) {
          legacyExports.push(statement.getText(source));
        }
      }
    }
    if (legacyExports.length > 0) {
      violations.push(`legacy exports: ${legacyExports.join(" ")}`);
    }

    expect(violations).toEqual([]);
  });

  it("rejects wildcard compatibility re-exports from a retired owner path", () => {
    const roots = [
      path.join(packageRoot, "src/primitives"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));
    const shimPath = path.join(
      dashboardRoot,
      "src/shared/ui/FoundationCompatibilityShim.ts",
    );
    units.push(sourceUnit(shimPath, 'export * from "@polisyos/atlas-ui";'));
    const relativeShimPath = path.join(
      dashboardRoot,
      "src/shared/ui/RelativeFoundationCompatibilityShim.ts",
    );
    const relativePackageSpecifier = path.relative(
      path.dirname(relativeShimPath),
      packageRoot,
    );
    units.push(
      sourceUnit(
        relativeShimPath,
        `export * from ${JSON.stringify(relativePackageSpecifier)};`,
      ),
    );

    expect(foundationOwnershipViolations(units)).toEqual(
      expect.arrayContaining([
        "package re-export: apps/runtime-dashboard/src/shared/ui/FoundationCompatibilityShim.ts -> @polisyos/atlas-ui",
        `package re-export: apps/runtime-dashboard/src/shared/ui/RelativeFoundationCompatibilityShim.ts -> ${relativePackageSpecifier}`,
      ]),
    );
  });
});
