import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const sourceRoot = path.resolve(import.meta.dirname, "../../..");
const applicationRoot = path.dirname(sourceRoot);
const repositoryRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], {
  cwd: applicationRoot,
  encoding: "utf8",
}).trim();

function isProductionTypeScript(file: string): boolean {
  const relative = path.relative(sourceRoot, file).split(path.sep).join("/");
  return (
    /\.(?:ts|tsx)$/.test(relative) &&
    !/\.(?:test|stories)\.(?:ts|tsx)$/.test(relative) &&
    !relative.startsWith("test/")
  );
}

function walk(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(entryPath) : [entryPath];
  });
}

function productionPopulation(): string[] {
  const filesystem = walk(sourceRoot).filter(isProductionTypeScript).sort();
  const sourcePrefix = path.relative(repositoryRoot, sourceRoot);
  const tracked = execFileSync("git", ["ls-files", "--", sourcePrefix], {
    cwd: repositoryRoot,
    encoding: "utf8",
  })
    .split("\n")
    .filter(Boolean)
    .map((file) => path.join(repositoryRoot, file))
    .filter(isProductionTypeScript)
    .sort();

  expect(filesystem).toEqual(tracked);
  return filesystem;
}

type ConsumerCensus = {
  directClientCalls: string[];
  hookCalls: string[];
  legacyDeclarations: string[];
  legacyProps: string[];
  renderers: string[];
};

function relativeSource(file: string): string {
  return path.relative(sourceRoot, file).split(path.sep).join("/");
}

function unalias(checker: ts.TypeChecker, symbol: ts.Symbol | undefined) {
  let current = symbol;
  const seen = new Set<ts.Symbol>();
  while (
    current &&
    (current.flags & ts.SymbolFlags.Alias) !== 0 &&
    !seen.has(current)
  ) {
    seen.add(current);
    current = checker.getAliasedSymbol(current);
  }
  return current;
}

function resolvedSymbol(checker: ts.TypeChecker, node: ts.Node) {
  const direct = checker.getSymbolAtLocation(node);
  if (direct) {
    return unalias(checker, direct);
  }
  if (ts.isPropertyAccessExpression(node)) {
    return unalias(checker, checker.getSymbolAtLocation(node.name));
  }
  return undefined;
}

function comesFrom(
  checker: ts.TypeChecker,
  node: ts.Node,
  exportName: string,
  sourceSuffix: string,
) {
  const symbol = resolvedSymbol(checker, node);
  return (
    symbol?.getName() === exportName &&
    (symbol.declarations ?? []).some((declaration) =>
      declaration
        .getSourceFile()
        .fileName.split(path.sep)
        .join("/")
        .endsWith(sourceSuffix),
    )
  );
}

type SymbolAliases = {
  client: Set<ts.Symbol>;
  factory: Set<ts.Symbol>;
  hook: Set<ts.Symbol>;
  renderer: Set<ts.Symbol>;
};

const canonicalSymbols = {
  client: {
    exportName: "getDepthNCycleBoardProjection",
    sourceSuffix: "/packages/runtime-api-client/runtimeApiClient.ts",
  },
  factory: {
    exportName: "createElement",
    sourceSuffix: "/node_modules/@types/react/index.d.ts",
  },
  hook: {
    exportName: "useDepthNCycleBoardProjection",
    sourceSuffix: "/features/runs/api/useDepthNCycleBoardProjection.ts",
  },
  renderer: {
    exportName: "CycleBoard",
    sourceSuffix: "/features/runs/components/CycleBoard.tsx",
  },
} as const;

function matchesSymbol(
  checker: ts.TypeChecker,
  node: ts.Node,
  kind: keyof SymbolAliases,
  aliases: SymbolAliases,
) {
  const symbol = resolvedSymbol(checker, node);
  const canonical = canonicalSymbols[kind];
  return (
    (symbol !== undefined && aliases[kind].has(symbol)) ||
    comesFrom(checker, node, canonical.exportName, canonical.sourceSuffix)
  );
}

function collectLocalAliases(
  checker: ts.TypeChecker,
  sources: readonly ts.SourceFile[],
) {
  const aliases: SymbolAliases = {
    client: new Set(),
    factory: new Set(),
    hook: new Set(),
    renderer: new Set(),
  };
  let changed = true;
  while (changed) {
    changed = false;
    const bind = (target: ts.Node, source: ts.Node) => {
      const targetSymbol = checker.getSymbolAtLocation(target);
      if (!targetSymbol) {
        return;
      }
      for (const kind of Object.keys(aliases) as (keyof SymbolAliases)[]) {
        if (
          matchesSymbol(checker, source, kind, aliases) &&
          !aliases[kind].has(targetSymbol)
        ) {
          aliases[kind].add(targetSymbol);
          changed = true;
        }
      }
    };
    const visit = (node: ts.Node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer
      ) {
        bind(node.name, node.initializer);
      }
      if (ts.isPropertyAssignment(node)) {
        bind(node.name, node.initializer);
      }
      if (ts.isPropertyDeclaration(node) && node.initializer) {
        bind(node.name, node.initializer);
      }
      if (ts.isShorthandPropertyAssignment(node)) {
        const targetSymbol = checker.getSymbolAtLocation(node.name);
        const valueSymbol = unalias(
          checker,
          checker.getShorthandAssignmentValueSymbol(node),
        );
        if (targetSymbol && valueSymbol) {
          for (const kind of Object.keys(aliases) as (keyof SymbolAliases)[]) {
            const canonical = canonicalSymbols[kind];
            const valueMatches =
              aliases[kind].has(valueSymbol) ||
              (valueSymbol.getName() === canonical.exportName &&
                (valueSymbol.declarations ?? []).some((declaration) =>
                  declaration
                    .getSourceFile()
                    .fileName.split(path.sep)
                    .join("/")
                    .endsWith(canonical.sourceSuffix),
                ));
            if (valueMatches && !aliases[kind].has(targetSymbol)) {
              aliases[kind].add(targetSymbol);
              changed = true;
            }
          }
        }
      }
      if (
        ts.isBindingElement(node) &&
        ts.isIdentifier(node.name) &&
        node.propertyName
      ) {
        bind(node.name, node.propertyName);
      }
      if (
        ts.isBinaryExpression(node) &&
        node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
        (ts.isIdentifier(node.left) || ts.isPropertyAccessExpression(node.left))
      ) {
        bind(node.left, node.right);
      }
      ts.forEachChild(node, visit);
    };
    for (const source of sources) {
      visit(source);
    }
  }
  return aliases;
}

function propertyName(node: ts.Node | undefined) {
  if (
    node &&
    (ts.isIdentifier(node) ||
      ts.isStringLiteral(node) ||
      ts.isNumericLiteral(node))
  ) {
    return node.text;
  }
  return null;
}

function inspectConsumers(files: string[]): ConsumerCensus {
  const configPath = path.join(applicationRoot, "tsconfig.app.json");
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error) {
    throw new Error(
      ts.flattenDiagnosticMessageText(config.error.messageText, "\n"),
    );
  }
  const parsed = ts.parseJsonConfigFileContent(
    config.config,
    ts.sys,
    applicationRoot,
  );
  const program = ts.createProgram({
    rootNames: files,
    options: parsed.options,
  });
  const checker = program.getTypeChecker();
  const sources = files.map((file) => {
    const source = program.getSourceFile(file);
    if (!source) {
      throw new Error(`TypeScript program omitted production source ${file}`);
    }
    return source;
  });
  const aliases = collectLocalAliases(checker, sources);
  const census: ConsumerCensus = {
    directClientCalls: [],
    hookCalls: [],
    legacyDeclarations: [],
    legacyProps: [],
    renderers: [],
  };

  for (const source of sources) {
    const file = source.fileName;
    const owner = relativeSource(file);
    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node)) {
        if (matchesSymbol(checker, node.expression, "hook", aliases)) {
          census.hookCalls.push(owner);
        }
        if (matchesSymbol(checker, node.expression, "client", aliases)) {
          census.directClientCalls.push(owner);
        }
        if (
          matchesSymbol(checker, node.expression, "factory", aliases) &&
          node.arguments[0] &&
          matchesSymbol(checker, node.arguments[0], "renderer", aliases)
        ) {
          census.renderers.push(owner);
        }
      }
      if (
        (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        matchesSymbol(checker, node.tagName, "renderer", aliases)
      ) {
        census.renderers.push(owner);
      }
      if (
        (ts.isFunctionDeclaration(node) ||
          ts.isClassDeclaration(node) ||
          ts.isVariableDeclaration(node)) &&
        propertyName(node.name) === "GovernedDepthProjection"
      ) {
        census.legacyDeclarations.push(owner);
      }
      if (
        ((ts.isJsxAttribute(node) ||
          ts.isPropertyAssignment(node) ||
          ts.isPropertySignature(node) ||
          ts.isPropertyDeclaration(node) ||
          ts.isBindingElement(node)) &&
          (propertyName(node.name) === "governedProjection" ||
            (ts.isBindingElement(node) &&
              propertyName(node.propertyName) === "governedProjection"))) ||
        (ts.isPropertyAccessExpression(node) &&
          node.name.text === "governedProjection")
      ) {
        census.legacyProps.push(owner);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }

  return census;
}

describe("Cycle Board production consumer census", () => {
  it("has one page that owns the sole resolved hook call and renderer", () => {
    const census = inspectConsumers(productionPopulation());

    expect(census.hookCalls).toEqual([
      "features/runs/routes/CycleBoardPage.tsx",
    ]);
    expect(census.renderers).toEqual([
      "features/runs/routes/CycleBoardPage.tsx",
    ]);
    expect(census.directClientCalls).toEqual([
      "features/runs/api/useDepthNCycleBoardProjection.ts",
    ]);
    expect(census.legacyDeclarations).toEqual([]);
    expect(census.legacyProps).toEqual([]);
  });
});
