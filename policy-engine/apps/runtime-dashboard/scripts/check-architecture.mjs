import fs from "node:fs/promises";
import path from "node:path";
import ts from "typescript";

const projectRoot = process.cwd();
const srcRoot = path.join(projectRoot, "src");
const supportedExtensions = [".ts", ".tsx", ".js", ".jsx", ".mjs"];

async function listFiles(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const resolved = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        return listFiles(resolved);
      }
      if (!supportedExtensions.includes(path.extname(entry.name))) {
        return [];
      }
      return [resolved];
    }),
  );

  return files.flat();
}

function tryResolveLocalImport(importPath) {
  const candidates = [
    importPath,
    ...supportedExtensions.map((extension) => `${importPath}${extension}`),
    ...supportedExtensions.map((extension) =>
      path.join(importPath, `index${extension}`),
    ),
  ];

  return (
    candidates.find((candidate) => {
      try {
        return ts.sys.fileExists(candidate);
      } catch {
        return false;
      }
    }) ?? null
  );
}

function resolveImport(fromFile, specifier) {
  if (specifier.startsWith("@/")) {
    return tryResolveLocalImport(path.join(srcRoot, specifier.slice(2)));
  }
  if (specifier.startsWith(".")) {
    return tryResolveLocalImport(
      path.resolve(path.dirname(fromFile), specifier),
    );
  }
  return null;
}

function relativePath(filePath) {
  return path.relative(projectRoot, filePath).replaceAll(path.sep, "/");
}

function classifyModule(filePath) {
  const relative = relativePath(filePath);

  if (relative.startsWith("src/features/")) {
    const [, , featureName] = relative.split("/");
    return {
      featureName,
      kind: "feature",
      relative,
    };
  }

  if (relative.startsWith("src/app/state/")) {
    return { kind: "app-state", relative };
  }
  if (relative.startsWith("src/app/providers/")) {
    return { kind: "app-provider", relative };
  }
  if (relative.startsWith("src/app/")) {
    return { kind: "app", relative };
  }
  if (relative.startsWith("src/api/")) {
    return { kind: "api", relative };
  }
  if (relative.startsWith("src/shared/lib/")) {
    return { kind: "shared-lib", relative };
  }
  if (relative.startsWith("src/shared/i18n/")) {
    return { kind: "shared-i18n", relative };
  }
  if (relative.startsWith("src/lib/")) {
    return { kind: "legacy-lib", relative };
  }
  if (relative.startsWith("src/i18n/")) {
    return { kind: "legacy-i18n", relative };
  }
  if (relative.startsWith("src/shared/")) {
    return { kind: "shared", relative };
  }
  if (relative.startsWith("src/pages/")) {
    return { kind: "legacy-pages", relative };
  }
  if (relative.startsWith("src/components/")) {
    return { kind: "legacy-components", relative };
  }

  return { kind: "other", relative };
}

function isFeaturePublicEntry(filePath) {
  const relative = relativePath(filePath);
  return (
    /^src\/features\/[^/]+\/index\.ts$/.test(relative) ||
    /^src\/features\/[^/]+\/index\.tsx$/.test(relative) ||
    /^src\/features\/[^/]+\/routes\.public\.ts$/.test(relative) ||
    /^src\/features\/[^/]+\/routes\.public\.tsx$/.test(relative)
  );
}

function collectImportRecords(filePath, sourceText) {
  const sourceFile = ts.createSourceFile(
    filePath,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
  );
  const records = [];

  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.moduleSpecifier.getStart(),
      );
      records.push({
        line: line + 1,
        specifier: node.moduleSpecifier.text,
      });
    }

    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.arguments[0].getStart(),
      );
      records.push({
        line: line + 1,
        specifier: node.arguments[0].text,
      });
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return records;
}

function validateImport(fromFile, toFile) {
  const from = classifyModule(fromFile);
  const to = classifyModule(toFile);
  const fromAppLayer =
    from.kind === "app" ||
    from.kind === "app-provider" ||
    from.kind === "app-state";
  const toAppLayer =
    to.kind === "app" ||
    to.kind === "app-provider" ||
    to.kind === "app-state";

  if (to.kind === "legacy-pages" || to.kind === "legacy-components") {
    return "Legacy src/pages and src/components modules cannot be imported.";
  }

  if (from.kind === "app-state" && to.kind === "app-provider") {
    return "app/state stores cannot depend on app/providers; providers may read stores.";
  }

  if (
    (from.kind === "shared" ||
      from.kind === "shared-lib" ||
      from.kind === "shared-i18n") &&
    (toAppLayer || to.kind === "feature")
  ) {
    return "shared layer cannot depend on app or features.";
  }

  if (
    from.kind === "shared-lib" &&
    (toAppLayer || to.kind === "feature" || to.kind === "shared")
  ) {
    return "shared/lib layer cannot depend on app, features, or shared UI.";
  }

  if (
    from.kind === "feature" &&
    to.kind === "feature" &&
    from.featureName !== to.featureName &&
    !isFeaturePublicEntry(toFile)
  ) {
    return `feature "${from.featureName}" can import feature "${to.featureName}" only via its public index.ts barrel.`;
  }

  if (
    fromAppLayer &&
    to.kind === "feature" &&
    !isFeaturePublicEntry(toFile)
  ) {
    return "app layer can import features only through their public index.ts barrel.";
  }

  return null;
}

function validateFileLocation(filePath) {
  const module = classifyModule(filePath);

  if (module.kind === "legacy-pages" || module.kind === "legacy-components") {
    return "Legacy src/pages and src/components modules must not exist on disk.";
  }

  if (module.kind === "legacy-lib" || module.kind === "legacy-i18n") {
    return "Legacy src/lib and src/i18n modules must live under src/shared.";
  }

  return null;
}

async function main() {
  const files = await listFiles(srcRoot);
  const violations = [];

  for (const filePath of files) {
    const locationError = validateFileLocation(filePath);
    if (locationError) {
      violations.push(`${relativePath(filePath)} :: ${locationError}`);
    }

    const sourceText = await fs.readFile(filePath, "utf8");
    const imports = collectImportRecords(filePath, sourceText);

    for (const record of imports) {
      const resolved = resolveImport(filePath, record.specifier);
      if (!resolved) {
        continue;
      }
      const error = validateImport(filePath, resolved);
      if (!error) {
        continue;
      }
      violations.push(
        `${relativePath(filePath)}:${record.line} -> ${record.specifier} :: ${error}`,
      );
    }
  }

  if (violations.length > 0) {
    console.error("Architecture violations detected:");
    for (const violation of violations) {
      console.error(`- ${violation}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log("Architecture checks passed.");
}

await main();
