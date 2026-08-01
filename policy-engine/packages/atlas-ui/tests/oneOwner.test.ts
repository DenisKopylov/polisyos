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

const FORM_FAMILIES = {
  Checkbox: ["Checkbox"],
  Input: ["Input"],
  Label: ["Label"],
  Radio: ["Radio"],
  SegmentedControl: ["SegmentedControl"],
  Select: ["Select"],
  Slider: ["Slider"],
  Switch: ["Switch"],
  Textarea: ["Textarea"],
  ToggleButton: ["ToggleButton"],
} as const;

const OVERLAY_FAMILIES = {
  Command: [
    "Command",
    "CommandDialog",
    "CommandEmpty",
    "CommandGroup",
    "CommandInput",
    "CommandItem",
    "CommandList",
    "CommandSeparator",
    "CommandShortcut",
  ],
  Dialog: [
    "Dialog",
    "DialogClose",
    "DialogContent",
    "DialogDescription",
    "DialogFooter",
    "DialogHeader",
    "DialogOverlay",
    "DialogPortal",
    "DialogTitle",
    "DialogTrigger",
  ],
  Popover: ["Popover", "PopoverAnchor", "PopoverContent", "PopoverTrigger"],
  Tooltip: ["Tooltip", "TooltipContent", "TooltipProvider", "TooltipTrigger"],
} as const;

const EVIDENCE_FAMILIES = {
  AuthorityBadge: ["AuthorityBadge"],
  EnvelopeChip: ["EnvelopeChip"],
  EvidenceLink: ["EvidenceLink"],
} as const;

const COMPOUND_FAMILIES = {
  JsonPreview: ["JsonPreview"],
  VirtualList: ["VirtualList", "VIRTUALIZATION_THRESHOLD"],
  VirtualTable: ["VirtualTable"],
} as const;

const PATTERN_FAMILIES = {
  DetailLayout: ["DetailLayout"],
  FilterPanel: ["FilterPanel"],
} as const;

type PrimitiveFamilies = Record<string, readonly string[]>;

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

function exportedNames(file: string, source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  const isExported = (node: ts.Node) =>
    ts.canHaveModifiers(node) &&
    ts
      .getModifiers(node)
      ?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword);
  const isDefaultExport = (node: ts.Node) =>
    ts.canHaveModifiers(node) &&
    ts
      .getModifiers(node)
      ?.some((modifier) => modifier.kind === ts.SyntaxKind.DefaultKeyword);
  const fileOwnerName = path.parse(file).name;

  for (const statement of source.statements) {
    if (
      (ts.isFunctionDeclaration(statement) ||
        ts.isClassDeclaration(statement) ||
        ts.isInterfaceDeclaration(statement) ||
        ts.isTypeAliasDeclaration(statement)) &&
      isExported(statement)
    ) {
      if (statement.name) {
        names.add(statement.name.text);
      }
      if (isDefaultExport(statement)) {
        names.add(fileOwnerName);
      }
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
        if (element.propertyName) {
          names.add(element.propertyName.text);
        }
        if (
          element.name.text === "default" ||
          element.propertyName?.text === "default"
        ) {
          names.add(fileOwnerName);
          if (
            statement.moduleSpecifier &&
            ts.isStringLiteral(statement.moduleSpecifier)
          ) {
            names.add(path.parse(statement.moduleSpecifier.text).name);
          }
        }
      }
    }
    if (ts.isExportAssignment(statement) && !statement.isExportEquals) {
      names.add("default");
      names.add(fileOwnerName);
      if (ts.isIdentifier(statement.expression)) {
        names.add(statement.expression.text);
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

function ownershipViolations(
  families: PrimitiveFamilies,
  units: SourceUnit[],
  ownerDirectory = "primitives",
): string[] {
  const violations: string[] = [];

  for (const [family, symbols] of Object.entries(families)) {
    const owners = units
      .filter(({ file, source }) => {
        const names = exportedNames(file, source);
        return symbols.some((symbol) => names.has(symbol));
      })
      .map(({ file }) => path.relative(productRoot, file))
      .sort();
    const expectedOwner = `packages/atlas-ui/src/${ownerDirectory}/${family}.tsx`;
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
    const violations = ownershipViolations(
      FOUNDATION_FAMILIES,
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

    expect(ownershipViolations(FOUNDATION_FAMILIES, units)).toEqual(
      expect.arrayContaining([
        "package re-export: apps/runtime-dashboard/src/shared/ui/FoundationCompatibilityShim.ts -> @polisyos/atlas-ui",
        `package re-export: apps/runtime-dashboard/src/shared/ui/RelativeFoundationCompatibilityShim.ts -> ${relativePackageSpecifier}`,
      ]),
    );
  });
});

describe("form primitive ownership", () => {
  it("rejects a duplicate form primitive owner while the old path still exports it", () => {
    const roots = [
      path.join(packageRoot, "src/primitives"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const files = roots.flatMap(walkTypeScriptFiles);
    const violations = ownershipViolations(
      FORM_FAMILIES,
      files.map((file) => sourceUnit(file)),
    );

    const legacyBarrel = path.join(
      dashboardRoot,
      "src/shared/ui/primitives/index.ts",
    );
    if (fs.existsSync(legacyBarrel)) {
      const legacyUnit = sourceUnit(legacyBarrel);
      for (const statement of legacyUnit.source.statements) {
        const moduleSpecifier = ts.isExportDeclaration(statement)
          ? statement.moduleSpecifier
          : undefined;
        if (
          moduleSpecifier &&
          ts.isStringLiteral(moduleSpecifier) &&
          Object.keys(FORM_FAMILIES).some(
            (family) => moduleSpecifier.text === `../${family}`,
          )
        ) {
          violations.push(
            `legacy export: ${statement.getText(legacyUnit.source)}`,
          );
        }
      }
    }

    expect(violations).toEqual([]);
  });
});

describe("overlay primitive ownership", () => {
  it("rejects a duplicate overlay primitive owner while the old path still exports it", () => {
    const roots = [
      path.join(packageRoot, "src/primitives"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const files = roots.flatMap(walkTypeScriptFiles);
    const violations = ownershipViolations(
      OVERLAY_FAMILIES,
      files.map((file) => sourceUnit(file)),
    );

    const legacyBarrel = path.join(
      dashboardRoot,
      "src/shared/ui/primitives/index.ts",
    );
    if (fs.existsSync(legacyBarrel)) {
      const legacyUnit = sourceUnit(legacyBarrel);
      for (const statement of legacyUnit.source.statements) {
        const moduleSpecifier = ts.isExportDeclaration(statement)
          ? statement.moduleSpecifier
          : undefined;
        if (
          moduleSpecifier &&
          ts.isStringLiteral(moduleSpecifier) &&
          Object.keys(OVERLAY_FAMILIES).some(
            (family) => moduleSpecifier.text === `../${family}`,
          )
        ) {
          violations.push(
            `legacy export: ${statement.getText(legacyUnit.source)}`,
          );
        }
      }
    }

    expect(violations).toEqual([]);
  });
});

describe("evidence primitive ownership", () => {
  it("rejects a migrated evidence primitive with a surviving dashboard implementation", () => {
    const roots = [
      path.join(packageRoot, "src/primitives"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));

    expect(ownershipViolations(EVIDENCE_FAMILIES, units)).toEqual([]);

    const duplicate = path.join(
      dashboardRoot,
      "src/shared/ui/AuthorityBadge.tsx",
    );
    const compatibilityShim = path.join(
      dashboardRoot,
      "src/shared/ui/EvidenceCompatibilityShim.ts",
    );
    const corruptedUnits = [
      ...units,
      sourceUnit(
        duplicate,
        "export function AuthorityBadge() { return null; }",
      ),
      sourceUnit(
        compatibilityShim,
        'export { EvidenceLink } from "@polisyos/atlas-ui";',
      ),
    ];

    expect(ownershipViolations(EVIDENCE_FAMILIES, corruptedUnits)).toEqual(
      expect.arrayContaining([
        expect.stringContaining("AuthorityBadge:"),
        "package re-export: apps/runtime-dashboard/src/shared/ui/EvidenceCompatibilityShim.ts -> @polisyos/atlas-ui",
      ]),
    );
  });
});

describe("compound ownership", () => {
  it("rejects a migrated compound with a surviving dashboard implementation", () => {
    const roots = [
      path.join(packageRoot, "src/compounds"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));

    expect(ownershipViolations(COMPOUND_FAMILIES, units, "compounds")).toEqual(
      [],
    );

    const duplicate = path.join(
      dashboardRoot,
      "src/shared/ui/VirtualTable.tsx",
    );
    const compatibilityShim = path.join(
      dashboardRoot,
      "src/shared/ui/CompoundCompatibilityShim.ts",
    );
    const corruptedUnits = [
      ...units,
      sourceUnit(duplicate, "export function VirtualTable() { return null; }"),
      sourceUnit(
        compatibilityShim,
        'export { JsonPreview } from "@polisyos/atlas-ui";',
      ),
    ];

    expect(
      ownershipViolations(COMPOUND_FAMILIES, corruptedUnits, "compounds"),
    ).toEqual(
      expect.arrayContaining([
        expect.stringContaining("VirtualTable:"),
        "package re-export: apps/runtime-dashboard/src/shared/ui/CompoundCompatibilityShim.ts -> @polisyos/atlas-ui",
      ]),
    );
  });

  it("rejects default-export compound owners and default re-exports", () => {
    const roots = [
      path.join(packageRoot, "src/compounds"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));
    const defaultOwner = path.join(
      dashboardRoot,
      "src/shared/ui/VirtualTable.tsx",
    );
    const defaultReexport = path.join(
      dashboardRoot,
      "src/shared/ui/JsonPreview.tsx",
    );
    const corruptedUnits = [
      ...units,
      sourceUnit(
        defaultOwner,
        "function LegacyVirtualTable() { return null; }\nexport default LegacyVirtualTable;",
      ),
      sourceUnit(
        defaultReexport,
        'export { default } from "./LegacyJsonPreview";',
      ),
    ];

    expect(
      ownershipViolations(COMPOUND_FAMILIES, corruptedUnits, "compounds"),
    ).toEqual(
      expect.arrayContaining([
        expect.stringContaining("JsonPreview:"),
        expect.stringContaining("VirtualTable:"),
      ]),
    );
  });

  it("binds anonymous default compound owners to their family filenames", () => {
    const roots = [
      path.join(packageRoot, "src/compounds"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));
    const anonymousFunctionOwner = path.join(
      dashboardRoot,
      "src/shared/ui/VirtualList.tsx",
    );
    const anonymousClassOwner = path.join(
      dashboardRoot,
      "src/shared/ui/JsonPreview.tsx",
    );
    const corruptedUnits = [
      ...units,
      sourceUnit(
        anonymousFunctionOwner,
        "export default function () { return null; }",
      ),
      sourceUnit(anonymousClassOwner, "export default class {}"),
    ];

    expect(
      ownershipViolations(COMPOUND_FAMILIES, corruptedUnits, "compounds"),
    ).toEqual(
      expect.arrayContaining([
        expect.stringContaining("JsonPreview:"),
        expect.stringContaining("VirtualList:"),
      ]),
    );
  });
});

describe("pattern ownership", () => {
  it("rejects a migrated pattern with a surviving dashboard implementation", () => {
    const roots = [
      path.join(packageRoot, "src/patterns"),
      path.join(dashboardRoot, "src/shared/ui"),
      path.join(dashboardRoot, "src/shared/components"),
    ];
    const units = roots
      .flatMap(walkTypeScriptFiles)
      .map((file) => sourceUnit(file));

    expect(ownershipViolations(PATTERN_FAMILIES, units, "patterns")).toEqual(
      [],
    );

    const namedOwner = path.join(
      dashboardRoot,
      "src/shared/ui/patterns/DetailLayout.tsx",
    );
    const defaultOwner = path.join(
      dashboardRoot,
      "src/shared/ui/patterns/FilterPanel.tsx",
    );
    const reexport = path.join(
      dashboardRoot,
      "src/shared/ui/PatternCompatibilityShim.ts",
    );
    const siblingOwner = path.join(
      dashboardRoot,
      "src/shared/components/WorkspacePatterns.tsx",
    );
    const corruptedUnits = [
      ...units,
      sourceUnit(
        namedOwner,
        "export function DetailLayout() { return null; }",
      ),
      sourceUnit(
        defaultOwner,
        "function LegacyFilterPanel() { return null; }\nexport default LegacyFilterPanel;",
      ),
      sourceUnit(
        reexport,
        'export { DetailLayout } from "@polisyos/atlas-ui";',
      ),
      sourceUnit(
        siblingOwner,
        "export const FilterPanel = () => null;",
      ),
    ];

    expect(
      ownershipViolations(PATTERN_FAMILIES, corruptedUnits, "patterns"),
    ).toEqual(
      expect.arrayContaining([
        expect.stringContaining("DetailLayout:"),
        expect.stringContaining("FilterPanel:"),
        "package re-export: apps/runtime-dashboard/src/shared/ui/PatternCompatibilityShim.ts -> @polisyos/atlas-ui",
      ]),
    );
  });
});
