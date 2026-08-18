#!/usr/bin/env node

import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const dashboardRoot = path.resolve(process.cwd(), "apps/runtime-dashboard");
const atlasUiRoot = path.resolve(process.cwd(), "packages/atlas-ui");
const repoRoot = process.cwd();
const require = createRequire(path.join(dashboardRoot, "package.json"));
const ts = require("typescript");

const CAPABILITY_DISCOVERY_OWNER_PATH =
  "apps/runtime-dashboard/src/api/hooks/useCapabilities.ts";
const CAPABILITY_TYPES_PATH = "apps/runtime-dashboard/src/api/types.ts";
const QUERY_KEYS_OWNER_PATH = "apps/runtime-dashboard/src/api/queryKeys.ts";
const DASHBOARD_SOURCE_PREFIX = "apps/runtime-dashboard/src/";
const TANSTACK_QUERY_CALLEES = new Set(["useQuery", "queryOptions"]);
const COMPOSER_DRAFT_DB_PATH =
  "apps/runtime-dashboard/src/app/offline/composerDraftDb.ts";
const COMPOSER_DRAFT_STORE = "composer-drafts";
const OPTIMISTIC_PROMOTION_OWNER_PATH =
  "apps/runtime-dashboard/src/api/hooks/usePromotionDecision.ts";
const OFFLINE_SERVICE_WORKER_PATH = "apps/runtime-dashboard/src/sw.ts";

function relativePath(fileName) {
  return path.relative(repoRoot, fileName).split(path.sep).join("/");
}

function isGeneratedDefinitionSource(fileName) {
  return relativePath(fileName) === "apps/runtime-dashboard/src/api/types.ts";
}

function isDefinitionSource(fileName) {
  const relative = relativePath(fileName);
  return (
    (relative.startsWith("apps/runtime-dashboard/src/") ||
      relative.startsWith("packages/atlas-ui/src/")) &&
    !isGeneratedDefinitionSource(fileName) &&
    !/\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$|\.stories\.[cm]?tsx?$/.test(
      relative,
    )
  );
}

function isOfflineQueueProductionSource(fileName) {
  const relative = relativePath(fileName);
  return (
    relative.startsWith(DASHBOARD_SOURCE_PREFIX) &&
    /\.tsx?$/.test(relative) &&
    isDefinitionSource(fileName)
  );
}

function isDashboardStatusInventorySource(fileName) {
  return (
    relativePath(fileName).startsWith(DASHBOARD_SOURCE_PREFIX) &&
    isDefinitionSource(fileName)
  );
}

function isDashboardPersistenceProductionSource(fileName) {
  const relative = relativePath(fileName);
  return (
    relative.startsWith(DASHBOARD_SOURCE_PREFIX) &&
    /\.tsx?$/.test(relative) &&
    !/(?:\.(?:a11y\.)?(?:test|spec)|\.stories)\.[cm]?tsx?$/.test(relative) &&
    !relative.includes("/src/test/")
  );
}

function lineOf(sourceFile, node) {
  return (
    sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
  );
}

function endLineOf(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getEnd()).line + 1;
}

function textSha256(value) {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function propertyNameText(name) {
  if (!name) return null;
  if (
    ts.isIdentifier(name) ||
    ts.isStringLiteral(name) ||
    ts.isNumericLiteral(name)
  ) {
    return name.text;
  }
  return null;
}

function stringUnionMembers(typeNode) {
  if (!typeNode || !ts.isUnionTypeNode(typeNode)) return null;
  const members = [];
  for (const member of typeNode.types) {
    if (ts.isLiteralTypeNode(member) && ts.isStringLiteral(member.literal)) {
      members.push(member.literal.text);
    }
  }
  const unique = [...new Set(members)].sort();
  return unique.length > 0 ? unique : null;
}

function stringLiteralTypeMembers(typeNode) {
  if (ts.isLiteralTypeNode(typeNode) && ts.isStringLiteral(typeNode.literal)) {
    return [typeNode.literal.text];
  }
  return stringUnionMembers(typeNode);
}

function importBindings(importDeclaration) {
  const bindings = [];
  const clause = importDeclaration.importClause;
  if (!clause) return bindings;
  if (clause.name) bindings.push(clause.name.text);
  if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
    for (const element of clause.namedBindings.elements) {
      bindings.push(element.name.text);
    }
  }
  return bindings.sort();
}

function declarationName(node) {
  if (
    (ts.isFunctionDeclaration(node) ||
      ts.isClassDeclaration(node) ||
      ts.isInterfaceDeclaration(node) ||
      ts.isTypeAliasDeclaration(node) ||
      ts.isEnumDeclaration(node)) &&
    node.name
  ) {
    return node.name.text;
  }
  return null;
}

function callName(node) {
  if (ts.isIdentifier(node)) return node.text;
  if (ts.isPropertyAccessExpression(node)) return node.name.text;
  return null;
}

function collectOfflineQueueFacts(sourceFiles, pathOf) {
  const facts = {
    authorityActionKinds: [],
    composerDbImports: [],
    mutationStores: [],
    optimisticAuthorityProjections: [],
    productionFiles: sourceFiles.length,
    replayDeclarations: [],
  };
  const queueDeclaration = /(queue|replay|offline.*mutation)/i;
  const authorityDeclaration = /(authority|promotion|mutation|offline)/i;

  for (const sourceFile of sourceFiles) {
    const relative = pathOf(sourceFile);
    const stringBindings = new Map();
    const collectStringBindings = (node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer &&
        ts.isStringLiteral(node.initializer)
      ) {
        stringBindings.set(node.name.text, node.initializer.text);
      }
      ts.forEachChild(node, collectStringBindings);
    };
    collectStringBindings(sourceFile);
    const visit = (node) => {
      if (
        ts.isImportDeclaration(node) &&
        ts.isStringLiteral(node.moduleSpecifier) &&
        node.moduleSpecifier.text.endsWith("app/offline/composerDraftDb")
      ) {
        facts.composerDbImports.push({
          bindings: importBindings(node),
          path: relative,
          targetPath: COMPOSER_DRAFT_DB_PATH,
        });
      }

      if (ts.isTypeAliasDeclaration(node) || ts.isEnumDeclaration(node)) {
        const name = declarationName(node);
        const members = ts.isTypeAliasDeclaration(node)
          ? stringLiteralTypeMembers(node.type)
          : enumMembers(node);
        if (name && members && queueDeclaration.test(name)) {
          facts.authorityActionKinds.push({
            kind: members.join(" | "),
            name,
            path: relative,
          });
        }
      }

      if (ts.isCallExpression(node)) {
        if (callName(node.expression) === "createObjectStore") {
          const store = node.arguments[0];
          const storeName =
            store && ts.isStringLiteral(store)
              ? store.text
              : store && ts.isIdentifier(store)
                ? (stringBindings.get(store.text) ?? "<dynamic-store>")
                : "<dynamic-store>";
          if (storeName !== COMPOSER_DRAFT_STORE) {
            facts.mutationStores.push({ path: relative, storeName });
          }
        }
        if (
          callName(node.expression) === "applyOptimisticPromotionDecision" &&
          relative !== OPTIMISTIC_PROMOTION_OWNER_PATH
        ) {
          facts.optimisticAuthorityProjections.push({ path: relative });
        }
      }

      const name = declarationName(node);
      if (
        name &&
        queueDeclaration.test(name) &&
        authorityDeclaration.test(name) &&
        relative !== OFFLINE_SERVICE_WORKER_PATH
      ) {
        facts.replayDeclarations.push({ name, path: relative });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  const compare = (left, right) =>
    JSON.stringify(left).localeCompare(JSON.stringify(right));
  for (const table of Object.values(facts)) {
    if (Array.isArray(table)) table.sort(compare);
  }
  return facts;
}

function persistenceDeclarationChain(node) {
  const chain = [];
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isFunctionDeclaration(current) && current.name) {
      chain.push(`function:${current.name.text}`);
    } else if (ts.isMethodDeclaration(current)) {
      chain.push(`method:${propertyNameText(current.name) ?? "<computed>"}`);
    } else if (ts.isConstructorDeclaration(current)) {
      chain.push("constructor");
    } else if (
      ts.isVariableDeclaration(current) &&
      ts.isIdentifier(current.name)
    ) {
      chain.push(`variable:${current.name.text}`);
    } else if (
      (ts.isPropertyDeclaration(current) ||
        ts.isPropertyAssignment(current) ||
        ts.isPropertySignature(current)) &&
      current.name
    ) {
      chain.push(`property:${propertyNameText(current.name) ?? "<computed>"}`);
    } else if (ts.isClassDeclaration(current) && current.name) {
      chain.push(`class:${current.name.text}`);
    }
  }
  return chain.reverse().join("/") || "module";
}

function persistenceDeclarationPaths(symbol) {
  return (symbol?.declarations ?? []).map((declaration) =>
    relativePath(declaration.getSourceFile().fileName),
  );
}

function persistenceDeclarationOwner(declaration) {
  for (let current = declaration?.parent; current; current = current.parent) {
    if (
      (ts.isInterfaceDeclaration(current) ||
        ts.isClassDeclaration(current) ||
        ts.isTypeAliasDeclaration(current)) &&
      current.name
    ) {
      return current.name.text;
    }
  }
  return null;
}

function persistenceApiForSymbol(symbol, operation) {
  const declarations = symbol?.declarations ?? [];
  const paths = persistenceDeclarationPaths(symbol);
  const isTypeScriptDom = paths.some(
    (candidate) =>
      candidate.endsWith("/typescript/lib/lib.dom.d.ts") ||
      candidate.endsWith("/@types/node/web-globals/storage.d.ts"),
  );
  const storageMember = declarations.some(
    (declaration) => persistenceDeclarationOwner(declaration) === "Storage",
  );
  if (
    isTypeScriptDom &&
    storageMember &&
    ["clear", "getItem", "key", "removeItem", "setItem"].includes(operation)
  ) {
    return {
      apiKind: "web_storage",
      resolvedApi: `typescript/lib/lib.dom.d.ts::Storage.${operation}`,
    };
  }
  if (
    paths.some(
      (candidate) =>
        candidate.includes("/zustand/") && candidate.includes("middleware"),
    ) &&
    ["createJSONStorage", "persist"].includes(operation)
  ) {
    return {
      apiKind: "zustand",
      resolvedApi: `zustand/middleware::${operation}`,
    };
  }
  if (
    paths.some(
      (candidate) =>
        candidate.includes("/idb/") && candidate.endsWith("/entry.d.ts"),
    ) &&
    ["createObjectStore", "delete", "get", "openDB", "put"].includes(operation)
  ) {
    return {
      apiKind: "indexed_db",
      resolvedApi: `idb::${operation}`,
    };
  }
  return null;
}

function localStorageApiForSymbol(symbol) {
  const declarations = symbol?.declarations ?? [];
  const paths = persistenceDeclarationPaths(symbol);
  const canonicalDeclaration = paths.some(
    (candidate) =>
      candidate.endsWith("/typescript/lib/lib.dom.d.ts") ||
      candidate.endsWith("/@types/node/web-globals/storage.d.ts"),
  );
  const localStorageDeclaration = declarations.some(
    (declaration) => propertyNameText(declaration.name) === "localStorage",
  );
  return canonicalDeclaration && localStorageDeclaration
    ? {
        apiKind: "web_storage",
        resolvedApi: "typescript/lib/lib.dom.d.ts::Window.localStorage",
      }
    : null;
}

function isAuthorityLocalStateFactorySymbol(symbol, operation) {
  if (
    ![
      "createAuthorityLocalStateEnvelopeFamily",
      "createAuthorityLocalStateFamily",
    ].includes(operation)
  ) {
    return false;
  }
  return persistenceDeclarationPaths(symbol).some(
    (candidate) =>
      candidate ===
      "apps/runtime-dashboard/src/app/offline/authorityLocalState.ts",
  );
}

function persistenceAccessName(expression) {
  if (ts.isIdentifier(expression)) return expression;
  if (ts.isPropertyAccessExpression(expression)) return expression.name;
  if (
    ts.isElementAccessExpression(expression) &&
    expression.argumentExpression &&
    ts.isStringLiteral(expression.argumentExpression)
  ) {
    return expression.argumentExpression;
  }
  return null;
}

function persistenceBindingSymbol(checker, binding, operation) {
  if (!ts.isBindingElement(binding)) return null;
  const pattern = binding.parent;
  if (!ts.isObjectBindingPattern(pattern)) return null;
  const declaration = pattern.parent;
  if (!ts.isVariableDeclaration(declaration) || !declaration.initializer) {
    return null;
  }
  const sourceType = checker.getTypeAtLocation(declaration.initializer);
  return checker.getPropertyOfType(sourceType, operation) ?? null;
}

function persistenceCalleeTarget(checker, expression, seen = new Set()) {
  const current = unwrapExpression(expression);
  if (seen.has(current)) return null;
  seen.add(current);

  if (ts.isCallExpression(current)) {
    const calledName = persistenceAccessName(current.expression)?.text ?? null;
    if (calledName === "bind") {
      const boundTarget =
        ts.isPropertyAccessExpression(current.expression) ||
        ts.isElementAccessExpression(current.expression)
          ? current.expression.expression
          : null;
      return boundTarget
        ? persistenceCalleeTarget(checker, boundTarget, seen)
        : null;
    }
    return null;
  }

  if (
    ts.isPropertyAccessExpression(current) ||
    ts.isElementAccessExpression(current)
  ) {
    const nameNode = persistenceAccessName(current);
    const operation = nameNode?.text ?? null;
    if (!operation) return null;
    if (["call", "apply"].includes(operation)) {
      return persistenceCalleeTarget(checker, current.expression, seen);
    }
    if (operation === "bind") return null;
    return {
      operation,
      symbol: resolvedSymbol(checker, nameNode),
    };
  }

  if (!ts.isIdentifier(current)) return null;
  const directSymbol = checker.getSymbolAtLocation(current);
  for (const declaration of directSymbol?.declarations ?? []) {
    if (ts.isVariableDeclaration(declaration) && declaration.initializer) {
      const target = persistenceCalleeTarget(
        checker,
        declaration.initializer,
        seen,
      );
      if (target) return target;
    }
    if (ts.isBindingElement(declaration)) {
      const operation =
        propertyNameText(declaration.propertyName) ??
        propertyNameText(declaration.name);
      const symbol = operation
        ? persistenceBindingSymbol(checker, declaration, operation)
        : null;
      if (operation && symbol) {
        return { operation, symbol };
      }
    }
  }
  return {
    operation: current.text,
    symbol: resolvedSymbol(checker, current),
  };
}

function isNestedPersistenceReceiver(node) {
  const parent = node.parent;
  if (
    (ts.isPropertyAccessExpression(parent) ||
      ts.isElementAccessExpression(parent)) &&
    parent.expression === node &&
    ts.isCallExpression(parent.parent) &&
    parent.parent.expression === parent
  ) {
    return true;
  }
  return false;
}

function enclosingFunctionLike(node) {
  let current = node.parent;
  while (current) {
    if (ts.isFunctionLike(current) && current.body) return current;
    current = current.parent;
  }
  return null;
}

function callableFunctionNodes(checker, expression, seen = new Set()) {
  const current = unwrapExpression(expression);
  if (seen.has(current)) return [];
  seen.add(current);
  if (ts.isFunctionLike(current) && current.body) return [current];
  if (ts.isConditionalExpression(current)) {
    return [
      ...callableFunctionNodes(checker, current.whenTrue, seen),
      ...callableFunctionNodes(checker, current.whenFalse, seen),
    ];
  }
  if (
    ts.isBinaryExpression(current) &&
    [
      ts.SyntaxKind.QuestionQuestionToken,
      ts.SyntaxKind.BarBarToken,
      ts.SyntaxKind.AmpersandAmpersandToken,
    ].includes(current.operatorToken.kind)
  ) {
    return [
      ...callableFunctionNodes(checker, current.left, seen),
      ...callableFunctionNodes(checker, current.right, seen),
    ];
  }
  const symbol = resolvedSymbol(checker, current);
  const functions = [];
  for (const declaration of symbol?.declarations ?? []) {
    if (ts.isFunctionLike(declaration) && declaration.body) {
      functions.push(declaration);
    } else if (
      (ts.isVariableDeclaration(declaration) ||
        ts.isPropertyAssignment(declaration) ||
        ts.isPropertyDeclaration(declaration)) &&
      declaration.initializer
    ) {
      functions.push(
        ...callableFunctionNodes(checker, declaration.initializer, seen),
      );
    }
  }
  return [...new Set(functions)];
}

function expressionReferencesAnySymbol(checker, expression, symbols) {
  let found = false;
  const visit = (node) => {
    if (found) return;
    if (ts.isIdentifier(node) && symbols.has(resolvedSymbol(checker, node))) {
      found = true;
      return;
    }
    ts.forEachChild(node, visit);
  };
  visit(expression);
  return found;
}

function variableDeclarationContaining(node) {
  let current = node.parent;
  while (current && !ts.isSourceFile(current)) {
    if (ts.isVariableDeclaration(current)) return current;
    current = current.parent;
  }
  return null;
}

function callsPropertyWithFactoryArgument(
  checker,
  scope,
  variableSymbol,
  propertyName,
  factoryIdsFromExpression,
) {
  const matched = new Set();
  const visit = (node) => {
    if (
      ts.isCallExpression(node) &&
      (ts.isPropertyAccessExpression(node.expression) ||
        ts.isElementAccessExpression(node.expression))
    ) {
      const access = node.expression;
      const name = persistenceAccessName(access)?.text ?? null;
      if (
        name === propertyName &&
        resolvedSymbol(checker, access.expression) === variableSymbol
      ) {
        for (const argument of node.arguments) {
          for (const factoryId of factoryIdsFromExpression(argument)) {
            matched.add(factoryId);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(scope.body ?? scope);
  return matched;
}

function collectPersistenceConstructionFacts(program, checker) {
  const productionSources = program
    .getSourceFiles()
    .filter((sourceFile) =>
      isDashboardPersistenceProductionSource(sourceFile.fileName),
    );
  const candidates = [];
  const authorityFactoryCandidates = [];
  for (const sourceFile of productionSources) {
    const pathOfSource = relativePath(sourceFile.fileName);
    const sourceSha256 = textSha256(sourceFile.text);
    const visit = (node) => {
      if (ts.isCallExpression(node)) {
        const target = persistenceCalleeTarget(checker, node.expression);
        const operation = target?.operation ?? null;
        const symbol = target?.symbol ?? null;
        const api = operation
          ? persistenceApiForSymbol(symbol, operation)
          : null;
        if (api) {
          candidates.push({
            node,
            operation,
            pathOfSource,
            sourceFile,
            sourceSha256,
            ...api,
          });
        }
        if (
          operation &&
          isAuthorityLocalStateFactorySymbol(symbol, operation)
        ) {
          authorityFactoryCandidates.push({
            node,
            operation,
            pathOfSource,
            sourceFile,
            sourceSha256,
          });
        }
      }

      const isLocalStorageAccess =
        (ts.isPropertyAccessExpression(node) ||
          ts.isElementAccessExpression(node)) &&
        persistenceAccessName(node)?.text === "localStorage";
      const isGlobalLocalStorageIdentifier =
        ts.isIdentifier(node) &&
        node.text === "localStorage" &&
        !(
          (ts.isPropertyAccessExpression(node.parent) ||
            ts.isElementAccessExpression(node.parent)) &&
          persistenceAccessName(node.parent) === node
        );
      if (
        (isLocalStorageAccess || isGlobalLocalStorageIdentifier) &&
        !isNestedPersistenceReceiver(node)
      ) {
        const nameNode = isLocalStorageAccess
          ? persistenceAccessName(node)
          : node;
        const api = localStorageApiForSymbol(resolvedSymbol(checker, nameNode));
        if (api) {
          candidates.push({
            node,
            operation: "acquire",
            pathOfSource,
            sourceFile,
            sourceSha256,
            ...api,
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  candidates.sort((left, right) =>
    `${left.pathOfSource}:${String(left.node.getStart(left.sourceFile)).padStart(12, "0")}`.localeCompare(
      `${right.pathOfSource}:${String(right.node.getStart(right.sourceFile)).padStart(12, "0")}`,
    ),
  );
  authorityFactoryCandidates.sort((left, right) =>
    `${left.pathOfSource}:${String(left.node.getStart(left.sourceFile)).padStart(12, "0")}`.localeCompare(
      `${right.pathOfSource}:${String(right.node.getStart(right.sourceFile)).padStart(12, "0")}`,
    ),
  );
  const factoryOrdinals = new Map();
  const authorityFactoryCalls = authorityFactoryCandidates.map((candidate) => {
    const declarationChain = persistenceDeclarationChain(candidate.node);
    const ordinalKey = [
      candidate.pathOfSource,
      declarationChain,
      candidate.operation,
    ].join("|");
    const ordinal = (factoryOrdinals.get(ordinalKey) ?? 0) + 1;
    factoryOrdinals.set(ordinalKey, ordinal);
    const stableKey = `${ordinalKey}|${ordinal}`;
    return {
      candidate,
      declarationChain,
      factory: candidate.operation,
      factorySiteId: `authority-factory-${createHash("sha256").update(stableKey).digest("hex")}`,
      path: candidate.pathOfSource,
      siteSha256: textSha256(candidate.node.getText(candidate.sourceFile)),
      sourceSha256: candidate.sourceSha256,
    };
  });
  const factoryByCall = new Map(
    authorityFactoryCalls.map((receipt) => [receipt.candidate.node, receipt]),
  );
  const factoryByOwnerSymbol = new Map();
  for (const receipt of authorityFactoryCalls) {
    let expression = receipt.candidate.node;
    while (
      expression.parent &&
      (ts.isParenthesizedExpression(expression.parent) ||
        ts.isAsExpression(expression.parent) ||
        ts.isSatisfiesExpression(expression.parent))
    ) {
      expression = expression.parent;
    }
    const declaration = expression.parent;
    if (
      ts.isVariableDeclaration(declaration) &&
      ts.isIdentifier(declaration.name)
    ) {
      const symbol = resolvedSymbol(checker, declaration.name);
      if (symbol) factoryByOwnerSymbol.set(symbol, receipt);
    }
  }
  const assignedExpressionsBySymbol = new Map();
  for (const sourceFile of productionSources) {
    const visitAssignments = (node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer
      ) {
        const symbol = resolvedSymbol(checker, node.name);
        if (symbol) {
          const values = assignedExpressionsBySymbol.get(symbol) ?? [];
          values.push(node.initializer);
          assignedExpressionsBySymbol.set(symbol, values);
        }
      } else if (
        ts.isBinaryExpression(node) &&
        node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
        ts.isIdentifier(unwrapExpression(node.left))
      ) {
        const symbol = resolvedSymbol(checker, unwrapExpression(node.left));
        if (symbol) {
          const values = assignedExpressionsBySymbol.get(symbol) ?? [];
          values.push(node.right);
          assignedExpressionsBySymbol.set(symbol, values);
        }
      }
      ts.forEachChild(node, visitAssignments);
    };
    visitAssignments(sourceFile);
  }

  const factoryIdsFromExpression = (expression, seen = new Set()) => {
    const current = unwrapExpression(expression);
    if (seen.has(current)) return new Set();
    seen.add(current);
    const ids = new Set();
    const directFactory = factoryByCall.get(current);
    if (directFactory) ids.add(directFactory.factorySiteId);
    if (ts.isIdentifier(current)) {
      const symbol = resolvedSymbol(checker, current);
      const owner = factoryByOwnerSymbol.get(symbol);
      if (owner) ids.add(owner.factorySiteId);
      for (const assigned of assignedExpressionsBySymbol.get(symbol) ?? []) {
        for (const factoryId of factoryIdsFromExpression(assigned, seen)) {
          ids.add(factoryId);
        }
      }
      for (const declaration of symbol?.declarations ?? []) {
        if (
          (ts.isVariableDeclaration(declaration) ||
            ts.isPropertyAssignment(declaration) ||
            ts.isPropertyDeclaration(declaration)) &&
          declaration.initializer
        ) {
          for (const factoryId of factoryIdsFromExpression(
            declaration.initializer,
            seen,
          )) {
            ids.add(factoryId);
          }
        }
      }
    }
    if (ts.isCallExpression(current)) {
      for (const functionNode of callableFunctionNodes(
        checker,
        current.expression,
      )) {
        for (const returned of functionReturnExpressions(functionNode)) {
          for (const factoryId of factoryIdsFromExpression(returned, seen)) {
            ids.add(factoryId);
          }
        }
      }
    }
    ts.forEachChild(current, (child) => {
      for (const factoryId of factoryIdsFromExpression(child, seen)) {
        ids.add(factoryId);
      }
    });
    return ids;
  };

  const factoryReceiptById = new Map(
    authorityFactoryCalls.map((receipt) => [receipt.factorySiteId, receipt]),
  );
  const functionBindings = new Map();
  const addFunctionBinding = (functionNode, factoryId, evidencePaths) => {
    if (!functionNode || !factoryReceiptById.has(factoryId)) return false;
    const byFactory = functionBindings.get(functionNode) ?? new Map();
    const paths = byFactory.get(factoryId) ?? new Set();
    const before = paths.size;
    for (const path of evidencePaths) paths.add(path);
    paths.add(relativePath(functionNode.getSourceFile().fileName));
    byFactory.set(factoryId, paths);
    functionBindings.set(functionNode, byFactory);
    return paths.size !== before;
  };
  const addFunctionAndLexicalAncestors = (
    functionNode,
    factoryId,
    evidencePaths,
  ) => {
    let changed = false;
    let current = functionNode;
    while (current) {
      changed =
        addFunctionBinding(current, factoryId, evidencePaths) || changed;
      let parent = current.parent;
      while (parent && !ts.isSourceFile(parent) && !ts.isFunctionLike(parent)) {
        parent = parent.parent;
      }
      current = parent && ts.isFunctionLike(parent) ? parent : null;
    }
    return changed;
  };
  for (const sourceFile of productionSources) {
    const visit = (node) => {
      if (ts.isCallExpression(node) && !factoryByCall.has(node)) {
        const ids = new Set();
        for (const argument of node.arguments) {
          for (const factoryId of factoryIdsFromExpression(argument)) {
            ids.add(factoryId);
          }
        }
        for (const factoryId of factoryIdsFromExpression(node.expression)) {
          ids.add(factoryId);
        }
        const functionNode = enclosingFunctionLike(node);
        for (const factoryId of ids) {
          const factory = factoryReceiptById.get(factoryId);
          addFunctionAndLexicalAncestors(functionNode, factoryId, [
            factory.path,
            relativePath(sourceFile.fileName),
          ]);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  let bindingChanged = true;
  while (bindingChanged) {
    bindingChanged = false;
    for (const sourceFile of productionSources) {
      const visit = (node) => {
        if (ts.isCallExpression(node)) {
          const caller = enclosingFunctionLike(node);
          const callerBindings = functionBindings.get(caller);
          if (callerBindings) {
            for (const called of callableFunctionNodes(
              checker,
              node.expression,
            )) {
              for (const [factoryId, evidencePaths] of callerBindings) {
                bindingChanged =
                  addFunctionAndLexicalAncestors(
                    called,
                    factoryId,
                    evidencePaths,
                  ) || bindingChanged;
              }
            }
          }
        }
        if (ts.isPropertyAssignment(node)) {
          const propertyName = propertyNameText(node.name);
          const variable = variableDeclarationContaining(node);
          const scope = variable ? enclosingFunctionLike(variable) : null;
          const scopeBindings = functionBindings.get(scope);
          const variableSymbol =
            variable && ts.isIdentifier(variable.name)
              ? resolvedSymbol(checker, variable.name)
              : null;
          if (propertyName && scopeBindings && variableSymbol) {
            const matched = callsPropertyWithFactoryArgument(
              checker,
              scope,
              variableSymbol,
              propertyName,
              factoryIdsFromExpression,
            );
            for (const target of callableFunctionNodes(
              checker,
              node.initializer,
            )) {
              for (const factoryId of matched) {
                const evidencePaths =
                  scopeBindings.get(factoryId) ??
                  new Set([relativePath(scope.getSourceFile().fileName)]);
                bindingChanged =
                  addFunctionAndLexicalAncestors(
                    target,
                    factoryId,
                    evidencePaths,
                  ) || bindingChanged;
              }
            }
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(sourceFile);
    }
    for (const receipt of authorityFactoryCalls) {
      const visitStorageProperties = (node) => {
        if (
          ts.isPropertyAssignment(node) &&
          propertyNameText(node.name) === "storage"
        ) {
          for (const target of callableFunctionNodes(
            checker,
            node.initializer,
          )) {
            bindingChanged =
              addFunctionAndLexicalAncestors(
                target,
                receipt.factorySiteId,
                [receipt.path],
              ) || bindingChanged;
          }
        }
        ts.forEachChild(node, visitStorageProperties);
      };
      for (const argument of receipt.candidate.node.arguments) {
        visitStorageProperties(argument);
      }
    }
  }

  const bindingForFunction = (functionNode) => {
    const combined = new Map();
    let current = functionNode;
    while (current) {
      for (const [factoryId, evidencePaths] of
        functionBindings.get(current) ?? []) {
        const paths = combined.get(factoryId) ?? new Set();
        for (const path of evidencePaths) paths.add(path);
        combined.set(factoryId, paths);
      }
      let parent = current.parent;
      while (parent && !ts.isSourceFile(parent) && !ts.isFunctionLike(parent)) {
        parent = parent.parent;
      }
      current = parent && ts.isFunctionLike(parent) ? parent : null;
    }
    return combined;
  };

  const ordinals = new Map();
  const sites = candidates.map((candidate) => {
    const declarationChain = persistenceDeclarationChain(candidate.node);
    const ordinalKey = [
      candidate.pathOfSource,
      declarationChain,
      candidate.resolvedApi,
      candidate.operation,
    ].join("|");
    const ordinal = (ordinals.get(ordinalKey) ?? 0) + 1;
    ordinals.set(ordinalKey, ordinal);
    const stableKey = `${ordinalKey}|${ordinal}`;
    const location = candidate.sourceFile.getLineAndCharacterOfPosition(
      candidate.node.getStart(candidate.sourceFile),
    );
    const site = {
      apiKind: candidate.apiKind,
      column: location.character + 1,
      declarationChain,
      line: location.line + 1,
      operation: candidate.operation,
      path: candidate.pathOfSource,
      resolvedApi: candidate.resolvedApi,
      siteId: `storage-site-${createHash("sha256").update(stableKey).digest("hex")}`,
      siteSha256: textSha256(candidate.node.getText(candidate.sourceFile)),
      sourceSha256: candidate.sourceSha256,
    };
    const callArguments = ts.isCallExpression(candidate.node)
      ? candidate.node.arguments
      : [];
    const argumentFactoryIds = callArguments.map((argument) =>
      factoryIdsFromExpression(argument),
    );
    const directFactoryIds = new Set();
    if (
      candidate.operation === "setItem" &&
      argumentFactoryIds.length >= 2
    ) {
      for (const factoryId of argumentFactoryIds[0]) {
        if (argumentFactoryIds[1].has(factoryId)) {
          directFactoryIds.add(factoryId);
        }
      }
    } else if (
      ["getItem", "removeItem"].includes(candidate.operation) &&
      argumentFactoryIds.length >= 1
    ) {
      for (const factoryId of argumentFactoryIds[0]) {
        directFactoryIds.add(factoryId);
      }
    } else {
      for (const ids of argumentFactoryIds) {
        for (const factoryId of ids) directFactoryIds.add(factoryId);
      }
    }
    const functionNode = enclosingFunctionLike(candidate.node);
    const functionBinding = bindingForFunction(functionNode);
    let proofKind = null;
    let boundFactoryIds = new Set();
    if (candidate.operation === "acquire") {
      proofKind = "storage_provider_flow";
      boundFactoryIds = new Set(functionBinding.keys());
    } else if (candidate.operation === "persist") {
      proofKind = "persistence_adapter_flow";
      boundFactoryIds = directFactoryIds;
    } else if (["openDB", "createObjectStore"].includes(candidate.operation)) {
      proofKind = "registered_transport_bootstrap";
      boundFactoryIds = new Set(functionBinding.keys());
    } else if (directFactoryIds.size > 0) {
      proofKind = "owner_derived_arguments";
      boundFactoryIds = directFactoryIds;
    } else if (
      ["get", "put", "delete"].includes(candidate.operation) &&
      functionNode
    ) {
      const parameterSymbols = new Set(
        functionNode.parameters.flatMap((parameter) =>
          bindingNames(parameter.name)
            .map((name) => resolvedSymbol(checker, name))
            .filter(Boolean),
        ),
      );
      if (
        callArguments.some((argument) =>
          expressionReferencesAnySymbol(checker, argument, parameterSymbols),
        )
      ) {
        proofKind = "registered_transport_parameter";
        boundFactoryIds = new Set(functionBinding.keys());
      }
    }
    if (proofKind && boundFactoryIds.size > 0) {
      const sourceFingerprints = new Map([
        [candidate.pathOfSource, candidate.sourceSha256],
      ]);
      for (const factoryId of boundFactoryIds) {
        const factory = factoryReceiptById.get(factoryId);
        if (factory) sourceFingerprints.set(factory.path, factory.sourceSha256);
        for (const path of functionBinding.get(factoryId) ?? []) {
          const sourceFile = productionSources.find(
            (candidateSource) => relativePath(candidateSource.fileName) === path,
          );
          if (sourceFile) sourceFingerprints.set(path, textSha256(sourceFile.text));
        }
      }
      const bindingReceipt = {
        factorySiteIds: [...boundFactoryIds].sort(),
        kind: proofKind,
        siteId: site.siteId,
        sourceFingerprints: [...sourceFingerprints]
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([path, sourceSha256]) => ({ path, sourceSha256 })),
      };
      site.authorityBinding = {
        factorySiteIds: bindingReceipt.factorySiteIds,
        proofKind,
        proofSha256: textSha256(JSON.stringify(bindingReceipt)),
        sourceFingerprints: bindingReceipt.sourceFingerprints,
      };
    } else {
      site.authorityBinding = null;
    }
    return site;
  });
  const apiCounts = { indexed_db: 0, web_storage: 0, zustand: 0 };
  for (const site of sites) apiCounts[site.apiKind] += 1;
  return {
    apiCounts,
    authorityFactoryCalls: authorityFactoryCalls.map(
      ({ candidate: _candidate, ...receipt }) => receipt,
    ),
    productionSourceCount: productionSources.length,
    residual:
      "direct declaration-resolved calls, acquisitions, and local destructured/bound aliases only; indirect storage value-flow remains not_established",
    sites,
  };
}

function enumMembers(node) {
  const members = [];
  for (const member of node.members) {
    if (!member.initializer || !ts.isStringLiteral(member.initializer))
      return [];
    members.push(member.initializer.text);
  }
  return [...new Set(members)].sort();
}

function inlineOwner(node) {
  const parent = node.parent;
  if (
    (ts.isPropertySignature(parent) ||
      ts.isPropertyDeclaration(parent) ||
      ts.isParameter(parent)) &&
    parent.type === node
  ) {
    return { fieldName: propertyNameText(parent.name), declaration: parent };
  }
  return null;
}

function isInlineStatusField(name) {
  return (
    typeof name === "string" &&
    (name === "status" || name.endsWith("_status") || name.endsWith("Status"))
  );
}

function semanticName(name) {
  return /(?:status|state|verdict|grade|disposition|freshness|readiness|authority|closure|verification|dispute|evidence|terminal|admissib|publishab|support|confidence|severity|risk|trust|tone|intent|profile|level|badgekind)/iu.test(
    name,
  );
}

function unwrapExpression(node) {
  let current = node;
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isTypeAssertionExpression(current) ||
    ts.isNonNullExpression(current) ||
    ts.isSatisfiesExpression(current) ||
    ts.isPartiallyEmittedExpression(current)
  ) {
    current = current.expression;
  }
  return current;
}

function resolvedSymbol(checker, node) {
  let symbol = checker.getSymbolAtLocation(node);
  while (symbol && (symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    const resolved = checker.getAliasedSymbol(symbol);
    if (!resolved || resolved === symbol) break;
    symbol = resolved;
  }
  return symbol;
}

function declarationIsNamedAtPath(node, name, expectedPath) {
  return (
    Boolean(node) &&
    relativePath(node.getSourceFile().fileName) === expectedPath &&
    ((node.name && propertyNameText(node.name) === name) ||
      (ts.isPropertySignature(node) && propertyNameText(node.name) === name))
  );
}

function symbolHasDeclaration(checker, symbol, predicate) {
  if (!symbol) return false;
  const candidates = [symbol];
  if ((symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    candidates.push(checker.getAliasedSymbol(symbol));
  }
  return candidates.some((candidate) =>
    (candidate?.declarations ?? []).some(predicate),
  );
}

function typeHasDeclaration(checker, type, predicate) {
  if (!type) return false;
  const symbols = [type.getSymbol(), type.aliasSymbol];
  return symbols.some((symbol) =>
    symbolHasDeclaration(checker, symbol, predicate),
  );
}

function typeHasCanonicalCapabilityFeature(checker, type) {
  return typeHasDeclaration(checker, type, (declaration) => {
    let current = declaration;
    while (current) {
      if (
        declarationIsNamedAtPath(
          current,
          "CapabilityFeatureInfo",
          CAPABILITY_TYPES_PATH,
        )
      ) {
        return true;
      }
      current = current.parent;
    }
    return false;
  });
}

function typeHasCanonicalCapabilityManifest(checker, type) {
  const features = checker.getPropertyOfType(type, "features");
  return symbolHasDeclaration(
    checker,
    features,
    (declaration) =>
      declarationIsNamedAtPath(
        declaration,
        "features",
        CAPABILITY_TYPES_PATH,
      ) &&
      declaration.parent &&
      ts.isTypeLiteralNode(declaration.parent) &&
      declaration.parent.parent &&
      declarationIsNamedAtPath(
        declaration.parent.parent,
        "CapabilityManifestResponse",
        CAPABILITY_TYPES_PATH,
      ),
  );
}

function objectProperty(node, name) {
  if (!ts.isObjectLiteralExpression(node)) return null;
  return (
    node.properties.find(
      (property) =>
        ts.isPropertyAssignment(property) &&
        propertyNameText(property.name) === name,
    ) ?? null
  );
}

function enclosingFunction(node) {
  let current = node.parent;
  while (current && !ts.isFunctionLike(current)) current = current.parent;
  return current ?? null;
}

function directCanonicalCapabilityManifestArgument(checker, typeNode) {
  if (!ts.isTypeReferenceNode(typeNode)) return false;
  const symbol = resolvedSymbol(checker, typeNode.typeName);
  return symbolHasDeclaration(
    checker,
    symbol,
    (declaration) =>
      ts.isTypeAliasDeclaration(declaration) &&
      declarationIsNamedAtPath(
        declaration,
        "CapabilityManifestResponse",
        CAPABILITY_DISCOVERY_OWNER_PATH,
      ) &&
      ts.isIndexedAccessTypeNode(declaration.type) &&
      typeHasCanonicalCapabilityManifest(
        checker,
        checker.getTypeFromTypeNode(declaration.type),
      ),
  );
}

function isReactQueryUseQueryResultDeclaration(declaration) {
  const normalized = declaration
    .getSourceFile()
    .fileName.split(path.sep)
    .join("/");
  return (
    (ts.isTypeAliasDeclaration(declaration) ||
      ts.isInterfaceDeclaration(declaration)) &&
    propertyNameText(declaration.name) === "UseQueryResult" &&
    /(?:^|\/)node_modules\/(?:\.pnpm\/[^/]+\/node_modules\/)?@tanstack\/react-query\//u.test(
      normalized,
    )
  );
}

function directCapabilityQueryParameter(checker, functionNode) {
  if (
    !functionNode ||
    !functionNode.name ||
    propertyNameText(functionNode.name) !== "discoverCapabilities"
  ) {
    return null;
  }
  for (const parameter of functionNode.parameters) {
    if (!ts.isIdentifier(parameter.name) || !parameter.type) continue;
    if (!ts.isTypeReferenceNode(parameter.type)) continue;
    const queryResult = resolvedSymbol(checker, parameter.type.typeName);
    const manifestArgument = parameter.type.typeArguments?.[0];
    if (
      symbolHasDeclaration(
        checker,
        queryResult,
        isReactQueryUseQueryResultDeclaration,
      ) &&
      manifestArgument &&
      directCanonicalCapabilityManifestArgument(checker, manifestArgument)
    ) {
      return parameter;
    }
  }
  return null;
}

function directCapabilityQueryData(checker, expression, functionNode) {
  if (
    !ts.isPropertyAccessExpression(expression) ||
    expression.name.text !== "data"
  ) {
    return false;
  }
  if (!ts.isIdentifier(expression.expression)) return false;
  const parameter = directCapabilityQueryParameter(checker, functionNode);
  return (
    parameter !== null &&
    resolvedSymbol(checker, expression.expression) ===
      resolvedSymbol(checker, parameter.name)
  );
}

function conditionTouchesCapabilityLoading(node, checker, parameter) {
  let touches = false;
  const parameterSymbol = resolvedSymbol(checker, parameter.name);
  const visit = (current) => {
    if (current !== node && ts.isFunctionLike(current)) return;
    if (
      ts.isPropertyAccessExpression(current) &&
      ts.isIdentifier(current.expression) &&
      resolvedSymbol(checker, current.expression) === parameterSymbol &&
      ["data", "isError", "isLoading", "isPaused", "isPending"].includes(
        current.name.text,
      )
    ) {
      touches = true;
      return;
    }
    ts.forEachChild(current, visit);
  };
  visit(node);
  return touches;
}

function availableCapabilityCallIsLoadingGuarded(checker, call, functionNode) {
  const parameter = directCapabilityQueryParameter(checker, functionNode);
  if (!parameter) return false;
  let current = call;
  while (current.parent && current.parent !== functionNode) {
    const parent = current.parent;
    if (
      ts.isIfStatement(parent) &&
      parent.thenStatement === current &&
      conditionTouchesCapabilityLoading(parent.expression, checker, parameter)
    ) {
      return true;
    }
    if (
      ts.isConditionalExpression(parent) &&
      parent.whenTrue === current &&
      conditionTouchesCapabilityLoading(parent.condition, checker, parameter)
    ) {
      return true;
    }
    current = parent;
  }
  return false;
}

function stringLiteralValue(node) {
  const current = unwrapExpression(node);
  return ts.isStringLiteral(current) ||
    ts.isNoSubstitutionTemplateLiteral(current)
    ? current.text
    : null;
}

function collectCapabilityDiscoveryFacts(sourceFiles, checker, pathOf) {
  const issuerCalls = [];
  const featureLiterals = [];
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (ts.isCallExpression(node)) {
        const issuer = resolvedSymbol(checker, node.expression);
        const isIssuer = symbolHasDeclaration(checker, issuer, (declaration) =>
          declarationIsNamedAtPath(
            declaration,
            "issueCapabilityDiscovery",
            CAPABILITY_DISCOVERY_OWNER_PATH,
          ),
        );
        if (isIssuer) {
          const argument =
            node.arguments.length === 1
              ? unwrapExpression(node.arguments[0])
              : null;
          const state = argument ? objectProperty(argument, "state") : null;
          const reason = argument ? objectProperty(argument, "reason") : null;
          const manifest = argument
            ? objectProperty(argument, "manifest")
            : null;
          const functionNode = enclosingFunction(node);
          issuerCalls.push({
            path: pathOf(sourceFile),
            line: lineOf(sourceFile, node),
            argumentKind:
              argument && ts.isObjectLiteralExpression(argument)
                ? "object_literal"
                : "other",
            state:
              state && ts.isPropertyAssignment(state)
                ? stringLiteralValue(state.initializer)
                : null,
            reason:
              reason && ts.isPropertyAssignment(reason)
                ? stringLiteralValue(reason.initializer)
                : null,
            manifest:
              manifest && ts.isPropertyAssignment(manifest)
                ? {
                    kind: ts.isObjectLiteralExpression(
                      unwrapExpression(manifest.initializer),
                    )
                      ? "object_literal"
                      : "expression",
                    canonical: typeHasCanonicalCapabilityManifest(
                      checker,
                      checker.getTypeAtLocation(manifest.initializer),
                    ),
                    directQueryData: directCapabilityQueryData(
                      checker,
                      manifest.initializer,
                      functionNode,
                    ),
                    loadingGuarded: availableCapabilityCallIsLoadingGuarded(
                      checker,
                      node,
                      functionNode,
                    ),
                  }
                : null,
          });
        }
      }
      if (ts.isObjectLiteralExpression(node)) {
        const contextual = checker.getContextualType(node);
        if (typeHasCanonicalCapabilityFeature(checker, contextual)) {
          featureLiterals.push({
            path: pathOf(sourceFile),
            line: lineOf(sourceFile, node),
            properties: node.properties
              .filter(ts.isPropertyAssignment)
              .map((property) => propertyNameText(property.name))
              .filter((name) => name !== null)
              .sort(),
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  const sortRows = (left, right) =>
    `${left.path}:${String(left.line).padStart(8, "0")}`.localeCompare(
      `${right.path}:${String(right.line).padStart(8, "0")}`,
    );
  return {
    issuerCalls: issuerCalls.sort(sortRows),
    featureLiterals: featureLiterals.sort(sortRows),
  };
}

function sourceSha256(sourceFile, node) {
  return textSha256(node.getText(sourceFile));
}

function tanstackQueryCallee(checker, expression) {
  const symbol = resolvedSymbol(checker, expression);
  if (!symbol || !TANSTACK_QUERY_CALLEES.has(symbol.getName())) return null;
  const declaredByTanstack = (symbol.declarations ?? []).some((declaration) =>
    /(?:^|\/)node_modules\/(?:\.pnpm\/[^/]+\/node_modules\/)?@tanstack\/react-query\//u.test(
      declaration.getSourceFile().fileName.split(path.sep).join("/"),
    ),
  );
  return declaredByTanstack ? symbol.getName() : null;
}

function queryKeyOwners(sourceFiles, checker) {
  const owners = new Map();
  for (const sourceFile of sourceFiles) {
    if (relativePath(sourceFile.fileName) !== QUERY_KEYS_OWNER_PATH) continue;
    const visit = (node) => {
      if (
        (ts.isMethodDeclaration(node) || ts.isPropertyAssignment(node)) &&
        node.parent &&
        ts.isObjectLiteralExpression(node.parent) &&
        node.parent.parent &&
        ts.isVariableDeclaration(node.parent.parent) &&
        node.parent.parent.name.getText(sourceFile) === "queryKeys"
      ) {
        const name = propertyNameText(node.name);
        const symbol = resolvedSymbol(checker, node.name);
        if (name && symbol) {
          owners.set(symbol, {
            name,
            path: QUERY_KEYS_OWNER_PATH,
            line: lineOf(sourceFile, node),
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return owners;
}

function directQueryKeyOwner(checker, initializer, owners) {
  const current = unwrapExpression(initializer);
  if (!ts.isCallExpression(current)) return null;
  const symbol = resolvedSymbol(checker, current.expression);
  if (symbol && owners.has(symbol)) return owners.get(symbol);
  if (!ts.isPropertyAccessExpression(current.expression)) return null;
  const ownerSymbol = resolvedSymbol(checker, current.expression.expression);
  const isCanonicalOwner = symbolHasDeclaration(
    checker,
    ownerSymbol,
    (declaration) =>
      ts.isVariableDeclaration(declaration) &&
      propertyNameText(declaration.name) === "queryKeys" &&
      relativePath(declaration.getSourceFile().fileName) ===
        QUERY_KEYS_OWNER_PATH,
  );
  if (!isCanonicalOwner) return null;
  return (
    [...owners.values()].find(
      (owner) => owner.name === current.expression.name.text,
    ) ?? null
  );
}

function queryKeyOwnerForObject(checker, object, owners) {
  const property = objectProperty(object, "queryKey");
  return property && ts.isPropertyAssignment(property)
    ? directQueryKeyOwner(checker, property.initializer, owners)
    : null;
}

function objectContainsSpreadAssignment(object) {
  return object.properties.some((property) => ts.isSpreadAssignment(property));
}

function optionsDeclarationFact(checker, options) {
  const current = unwrapExpression(options);
  if (!ts.isCallExpression(current)) return null;
  const symbol = resolvedSymbol(checker, current.expression);
  const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
  if (!symbol || !declaration) return null;
  return {
    name: symbol.getName(),
    path: relativePath(declaration.getSourceFile().fileName),
    line: lineOf(declaration.getSourceFile(), declaration),
  };
}

function enclosingOptionsDeclarationFact(node) {
  let current = node.parent;
  while (current) {
    if (ts.isFunctionDeclaration(current) && current.name) {
      return {
        name: current.name.text,
        path: relativePath(current.getSourceFile().fileName),
        line: lineOf(current.getSourceFile(), current),
      };
    }
    current = current.parent;
  }
  return null;
}

function isDirectTanstackQueryOptionsObject(checker, object) {
  const parent = object.parent;
  return (
    ts.isCallExpression(parent) &&
    parent.arguments.some(
      (argument) => unwrapExpression(argument) === object,
    ) &&
    tanstackQueryCallee(checker, parent.expression) !== null
  );
}

function queryContract(checker, node) {
  return checker.typeToString(
    checker.getTypeAtLocation(node),
    node,
    ts.TypeFormatFlags.NoTruncation | ts.TypeFormatFlags.UseFullyQualifiedType,
  );
}

function collectQueryCachePolicyFacts(sourceFiles, checker, pathOf) {
  const dashboardSources = sourceFiles.filter(
    (sourceFile) =>
      pathOf(sourceFile).startsWith(DASHBOARD_SOURCE_PREFIX) &&
      isDefinitionSource(sourceFile.fileName),
  );
  const owners = queryKeyOwners(sourceFiles, checker);
  const queryKeyOwnersRows = [...owners.values()]
    .map((owner) => ({ ...owner }))
    .sort((left, right) => left.name.localeCompare(right.name));
  const constructions = [];
  const producers = [];
  for (const sourceFile of dashboardSources) {
    const visit = (node) => {
      if (ts.isCallExpression(node)) {
        const callee = tanstackQueryCallee(checker, node.expression);
        if (callee) {
          const options =
            node.arguments.length === 1
              ? unwrapExpression(node.arguments[0])
              : null;
          const owner =
            options && ts.isObjectLiteralExpression(options)
              ? queryKeyOwnerForObject(checker, options, owners)
              : null;
          constructions.push({
            callee,
            path: pathOf(sourceFile),
            line: lineOf(sourceFile, node),
            sourceSha256: sourceSha256(sourceFile, node),
            queryKeyOwner: owner?.name ?? null,
            optionsDeclaration: options
              ? optionsDeclarationFact(checker, options)
              : null,
            optionsResolution:
              options &&
              ts.isObjectLiteralExpression(options) &&
              !objectContainsSpreadAssignment(options)
                ? "inline"
                : "referenced",
          });
        }
      }
      if (
        ts.isPropertyAssignment(node) &&
        propertyNameText(node.name) === "queryFn" &&
        ts.isObjectLiteralExpression(node.parent) &&
        !objectContainsSpreadAssignment(node.parent) &&
        (isDirectTanstackQueryOptionsObject(checker, node.parent) ||
          (ts.isReturnStatement(node.parent.parent) &&
            queryKeyOwnerForObject(checker, node.parent, owners) !== null))
      ) {
        const owner = queryKeyOwnerForObject(checker, node.parent, owners);
        producers.push({
          path: pathOf(sourceFile),
          line: lineOf(sourceFile, node),
          sourceSha256: sourceSha256(sourceFile, node),
          queryKeyOwner: owner?.name ?? null,
          dtoContract: queryContract(checker, node.initializer),
          optionsDeclaration: enclosingOptionsDeclarationFact(node),
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  const sortRows = (left, right) =>
    `${left.path}:${String(left.line).padStart(8, "0")}`.localeCompare(
      `${right.path}:${String(right.line).padStart(8, "0")}`,
    );
  return {
    residual:
      "direct construction-site declaration identity only; option-value semantics for referenced options are unestablished and no call is excluded, debt, or exempted on that basis",
    queryKeyOwners: queryKeyOwnersRows,
    constructions: constructions.sort(sortRows),
    producers: producers.sort(sortRows),
  };
}

function constAssertionOperand(node, sourceFile) {
  let current = node;
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isSatisfiesExpression(current)
  ) {
    current = current.expression;
  }
  if (
    (ts.isAsExpression(current) || ts.isTypeAssertionExpression(current)) &&
    current.type.getText(sourceFile) === "const"
  ) {
    return current.expression;
  }
  return null;
}

function constVocabularyMembers(node) {
  const members = [];
  const visit = (current) => {
    current = unwrapExpression(current);
    if (
      ts.isStringLiteral(current) ||
      ts.isNoSubstitutionTemplateLiteral(current)
    ) {
      members.push(current.text);
      return;
    }
    if (ts.isArrayLiteralExpression(current)) {
      for (const element of current.elements) visit(element);
      return;
    }
    if (ts.isObjectLiteralExpression(current)) {
      for (const property of current.properties) {
        if (
          ts.isPropertyAssignment(property) ||
          ts.isShorthandPropertyAssignment(property)
        ) {
          visit(
            ts.isPropertyAssignment(property)
              ? property.initializer
              : property.name,
          );
        }
      }
    }
  };
  visit(node);
  const unique = [...new Set(members)].sort();
  return unique.length > 1 ? unique : null;
}

function constVocabularyFact(node, sourceFile, pathName) {
  if (
    !ts.isVariableDeclaration(node) ||
    !ts.isIdentifier(node.name) ||
    !semanticName(node.name.text) ||
    !node.initializer
  ) {
    return null;
  }
  const operand = constAssertionOperand(node.initializer, sourceFile);
  const members = operand ? constVocabularyMembers(operand) : null;
  if (!members) return null;
  return {
    kind: "const",
    path: pathName,
    startLine: lineOf(sourceFile, node),
    endLine: endLineOf(sourceFile, node),
    declarationName: node.name.text,
    fieldName: null,
    members,
    typeExpression: node.initializer.getText(sourceFile),
  };
}

function functionLikeName(node) {
  if (node.name) {
    const declaredName = propertyNameText(node.name);
    if (declaredName) return declaredName;
  }
  const parent = node.parent;
  if (
    ts.isVariableDeclaration(parent) ||
    ts.isPropertyDeclaration(parent) ||
    ts.isPropertyAssignment(parent)
  ) {
    return propertyNameText(parent.name);
  }
  return null;
}

function semanticReturnFact(node, sourceFile, pathName) {
  if (
    !(
      ts.isFunctionDeclaration(node) ||
      ts.isFunctionExpression(node) ||
      ts.isArrowFunction(node) ||
      ts.isMethodDeclaration(node) ||
      ts.isMethodSignature(node) ||
      ts.isGetAccessorDeclaration(node)
    ) ||
    !node.type
  ) {
    return null;
  }
  const declarationName = functionLikeName(node);
  if (!declarationName || !semanticName(declarationName)) return null;
  const members = stringUnionMembers(node.type);
  if (!members) return null;
  return {
    kind: "return",
    path: pathName,
    startLine: lineOf(sourceFile, node),
    endLine: endLineOf(sourceFile, node),
    declarationName,
    fieldName: null,
    members,
    typeExpression: node.type.getText(sourceFile),
  };
}

function bindingNames(name) {
  if (ts.isIdentifier(name)) return [name];
  if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name)) {
    return name.elements.flatMap((element) =>
      ts.isOmittedExpression(element) ? [] : bindingNames(element.name),
    );
  }
  return [];
}

function functionReturnExpressions(node) {
  if (!node.body) return [];
  if (!ts.isBlock(node.body)) return [node.body];
  const expressions = [];
  const visit = (current) => {
    if (current !== node && ts.isFunctionLike(current)) return;
    if (ts.isReturnStatement(current) && current.expression) {
      expressions.push(current.expression);
      return;
    }
    ts.forEachChild(current, visit);
  };
  visit(node.body);
  return expressions;
}

function returnedStringMembers(node) {
  if (!ts.isFunctionLike(node)) return null;
  const members = [];
  const collect = (current) => {
    current = unwrapExpression(current);
    if (
      ts.isStringLiteral(current) ||
      ts.isNoSubstitutionTemplateLiteral(current)
    ) {
      members.push(current.text);
      return;
    }
    if (ts.isConditionalExpression(current)) {
      collect(current.whenTrue);
      collect(current.whenFalse);
      return;
    }
    ts.forEachChild(current, collect);
  };
  for (const expression of functionReturnExpressions(node)) collect(expression);
  const unique = [...new Set(members)].sort();
  return unique.length > 1 ? unique : null;
}

function genericVocabularyMembers(node, sourceFile) {
  if (ts.isUnionTypeNode(node)) return stringUnionMembers(node);
  if (ts.isEnumDeclaration(node)) return enumMembers(node);
  if (ts.isVariableDeclaration(node) && node.initializer) {
    const operand = constAssertionOperand(node.initializer, sourceFile);
    return operand ? constVocabularyMembers(operand) : null;
  }
  return returnedStringMembers(node);
}

const PRESENTATION_SINK_ATTRIBUTES = new Set([
  "badgeKind",
  "className",
  "color",
  "intent",
  "kind",
  "severity",
  "status",
  "style",
  "tone",
  "variant",
]);

const LAYOUT_ONLY_CLASS =
  /^(?:(?:[a-z0-9-]+):)*(?:(?:inline-)?grid|grid-(?:cols|rows)-\S+|(?:col|row)-(?:auto|span-\S+|start-\S+|end-\S+)|(?:inline-)?flex|block|inline|inline-block|hidden|contents|flow-root|items-\S+|justify-\S+|content-\S+|self-\S+|place-\S+|gap(?:-[xy])?-\S+|space-[xy]-\S+|order-\S+|basis-\S+|grow(?:-\S+)?|shrink(?:-\S+)?|[wh]-\S+|(?:min|max)-[wh]-\S+|[pm][trblxy]?-\S+|inset(?:-[xy])?-\S+|top-\S+|right-\S+|bottom-\S+|left-\S+|overflow(?:-[xy])?-\S+|static|fixed|absolute|relative|sticky)$/u;

function isLayoutOnlyClassVocabulary(members) {
  return [...members].every((member) => {
    const tokens = member.trim().split(/\s+/u).filter(Boolean);
    return (
      tokens.length > 0 &&
      tokens.every((token) => LAYOUT_ONLY_CLASS.test(token))
    );
  });
}

function containsThresholdComparison(node) {
  let found = false;
  const visit = (current) => {
    if (current !== node && ts.isFunctionLike(current)) return;
    if (
      ts.isBinaryExpression(current) &&
      [
        ts.SyntaxKind.GreaterThanToken,
        ts.SyntaxKind.GreaterThanEqualsToken,
        ts.SyntaxKind.LessThanToken,
        ts.SyntaxKind.LessThanEqualsToken,
      ].includes(current.operatorToken.kind)
    ) {
      found = true;
      return;
    }
    ts.forEachChild(current, visit);
  };
  visit(node);
  return found;
}

function mergePresentationFacts(...facts) {
  const members = new Set();
  const thresholdMembers = new Set();
  for (const fact of facts) {
    if (!fact) continue;
    for (const member of fact.members) members.add(member);
    for (const member of fact.thresholdMembers) thresholdMembers.add(member);
  }
  return members.size > 0 ? { members, thresholdMembers } : null;
}

function samePresentationFact(left, right) {
  if (!left || !right) return left === right;
  if (
    left.members.size !== right.members.size ||
    left.thresholdMembers.size !== right.thresholdMembers.size
  ) {
    return false;
  }
  return (
    [...left.members].every((member) => right.members.has(member)) &&
    [...left.thresholdMembers].every((member) =>
      right.thresholdMembers.has(member),
    )
  );
}

function commonPresentationMembers(facts) {
  const common = new Set(facts[0]?.members ?? []);
  for (const fact of facts.slice(1)) {
    for (const member of common) {
      if (!fact.members.has(member)) common.delete(member);
    }
  }
  return common;
}

function collectThresholdPresentationRevivals(
  sourceFile,
  matching,
  relative,
  checker,
) {
  const staticFacts = new Map();
  const functionFacts = new Map();
  const valueFacts = new Map();
  const objectFacts = new Map();
  const functionNodes = [];
  const variableNodes = [];
  const assignmentNodes = [];
  const propertyNodes = [];

  const binding = (node) => {
    if (!node) return undefined;
    const symbol = symbolIdentity(checker, node);
    const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
    return declaration
      ? `${declaration.getSourceFile().fileName}:${declaration.pos}:${declaration.end}:${symbol.name}`
      : undefined;
  };
  const functionBinding = (node) => {
    if (node.name) return binding(node.name);
    const parent = node.parent;
    if (
      ts.isVariableDeclaration(parent) ||
      ts.isPropertyAssignment(parent) ||
      ts.isPropertyDeclaration(parent)
    ) {
      return binding(parent.name);
    }
    return undefined;
  };
  const storeFact = (target, identity, fact) => {
    if (!identity || !fact) return false;
    const merged = mergePresentationFacts(target.get(identity), fact);
    if (samePresentationFact(target.get(identity), merged)) return false;
    target.set(identity, merged);
    return true;
  };

  const expressionFact = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return null;
    seen.add(current);
    if (
      ts.isStringLiteral(current) ||
      ts.isNoSubstitutionTemplateLiteral(current)
    ) {
      return {
        members: new Set([current.text]),
        thresholdMembers: new Set(),
      };
    }
    if (
      ts.isIdentifier(current) ||
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      const identity = binding(current);
      return identity
        ? (valueFacts.get(identity) ?? staticFacts.get(identity) ?? null)
        : null;
    }
    if (ts.isCallExpression(current)) {
      const callee = binding(current.expression);
      return mergePresentationFacts(
        callee ? functionFacts.get(callee) : null,
        ...current.arguments.map((argument) => expressionFact(argument, seen)),
      );
    }
    if (ts.isConditionalExpression(current)) {
      const branches = [
        expressionFact(current.whenTrue, seen),
        expressionFact(current.whenFalse, seen),
      ].filter(Boolean);
      const fact = mergePresentationFacts(...branches);
      if (fact && containsThresholdComparison(current.condition)) {
        const commonMembers = commonPresentationMembers(branches);
        const thresholdMembers = new Set(fact.thresholdMembers);
        for (const member of fact.members) {
          if (!commonMembers.has(member)) thresholdMembers.add(member);
        }
        return { ...fact, thresholdMembers };
      }
      return fact;
    }
    if (ts.isTemplateExpression(current)) {
      return mergePresentationFacts(
        ...current.templateSpans.map((span) =>
          expressionFact(span.expression, seen),
        ),
      );
    }
    if (
      ts.isAwaitExpression(current) ||
      ts.isYieldExpression(current) ||
      ts.isSpreadElement(current)
    ) {
      return current.expression
        ? expressionFact(current.expression, seen)
        : null;
    }
    if (ts.isBinaryExpression(current)) {
      if (
        [
          ts.SyntaxKind.EqualsEqualsToken,
          ts.SyntaxKind.EqualsEqualsEqualsToken,
          ts.SyntaxKind.ExclamationEqualsToken,
          ts.SyntaxKind.ExclamationEqualsEqualsToken,
          ts.SyntaxKind.GreaterThanToken,
          ts.SyntaxKind.GreaterThanEqualsToken,
          ts.SyntaxKind.LessThanToken,
          ts.SyntaxKind.LessThanEqualsToken,
        ].includes(current.operatorToken.kind)
      ) {
        return null;
      }
      return mergePresentationFacts(
        expressionFact(current.left, seen),
        expressionFact(current.right, seen),
      );
    }
    return null;
  };

  const discoverNodes = (node) => {
    if (ts.isFunctionLike(node)) functionNodes.push(node);
    if (ts.isVariableDeclaration(node)) variableNodes.push(node);
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken
    ) {
      assignmentNodes.push(node);
    }
    if (ts.isPropertyAssignment(node)) propertyNodes.push(node);
    ts.forEachChild(node, discoverNodes);
  };
  discoverNodes(sourceFile);

  let staticChanged = true;
  while (staticChanged) {
    staticChanged = false;
    for (const node of [...variableNodes, ...propertyNodes]) {
      if (!node.initializer) continue;
      const fact = expressionFact(node.initializer);
      if (fact && fact.thresholdMembers.size === 0) {
        staticChanged =
          storeFact(staticFacts, binding(node.name), fact) || staticChanged;
      }
    }
  }

  let changed = true;
  while (changed) {
    changed = false;
    for (const node of functionNodes) {
      const returnFacts = functionReturnExpressions(node)
        .map((expression) => expressionFact(expression))
        .filter(Boolean);
      const returned = mergePresentationFacts(...returnFacts);
      if (returned) {
        const bodyHasThreshold = Boolean(
          node.body && containsThresholdComparison(node.body),
        );
        const commonMembers = commonPresentationMembers(returnFacts);
        const fact = {
          members: returned.members,
          thresholdMembers:
            returned.thresholdMembers.size > 0
              ? returned.thresholdMembers
              : bodyHasThreshold
                ? new Set(
                    [...returned.members].filter(
                      (member) => !commonMembers.has(member),
                    ),
                  )
                : new Set(),
        };
        if (fact.thresholdMembers.size > 0) {
          changed =
            storeFact(functionFacts, functionBinding(node), fact) || changed;
        }
      }
    }
    for (const node of variableNodes) {
      if (!node.initializer) continue;
      const fact = expressionFact(node.initializer);
      if (fact && fact.thresholdMembers.size > 0) {
        changed = storeFact(valueFacts, binding(node.name), fact) || changed;
      }
    }
    for (const node of propertyNodes) {
      const fact = expressionFact(node.initializer);
      if (fact && fact.thresholdMembers.size > 0) {
        changed = storeFact(valueFacts, binding(node.name), fact) || changed;
      }
    }
    for (const node of assignmentNodes) {
      const fact = expressionFact(node.right);
      if (fact && fact.thresholdMembers.size > 0) {
        changed = storeFact(valueFacts, binding(node.left), fact) || changed;
      }
    }
  }
  const mergeObjectEntries = (...entryGroups) => {
    const entries = new Map();
    for (const group of entryGroups) {
      for (const entry of group ?? []) {
        const key = `${entry.attributeName}:${[...entry.fact.members]
          .sort()
          .join("\0")}:${[...entry.fact.thresholdMembers].sort().join("\0")}`;
        entries.set(key, entry);
      }
    }
    return [...entries.values()];
  };
  const objectEntries = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return [];
    seen.add(current);
    if (
      ts.isIdentifier(current) ||
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      const identity = binding(current);
      return identity ? (objectFacts.get(identity) ?? []) : [];
    }
    if (!ts.isObjectLiteralExpression(current)) return [];
    const entries = [];
    for (const property of current.properties) {
      if (ts.isSpreadAssignment(property)) {
        entries.push(...objectEntries(property.expression, seen));
        continue;
      }
      if (ts.isPropertyAssignment(property)) {
        const attributeName = propertyNameText(property.name);
        const fact = expressionFact(property.initializer);
        if (attributeName && fact && fact.thresholdMembers.size > 0) {
          entries.push({ attributeName, fact });
        }
        continue;
      }
      if (ts.isShorthandPropertyAssignment(property)) {
        const fact = expressionFact(property.name);
        if (fact && fact.thresholdMembers.size > 0) {
          entries.push({ attributeName: property.name.text, fact });
        }
      }
    }
    return entries;
  };

  let objectChanged = true;
  while (objectChanged) {
    objectChanged = false;
    for (const node of [...variableNodes, ...propertyNodes]) {
      if (!node.initializer) continue;
      const entries = objectEntries(node.initializer);
      const identity = binding(node.name);
      if (!identity || entries.length === 0) continue;
      const merged = mergeObjectEntries(objectFacts.get(identity), entries);
      if (merged.length !== (objectFacts.get(identity)?.length ?? 0)) {
        objectFacts.set(identity, merged);
        objectChanged = true;
      }
    }
    for (const node of assignmentNodes) {
      const entries = objectEntries(node.right);
      const identity = binding(node.left);
      if (!identity || entries.length === 0) continue;
      const merged = mergeObjectEntries(objectFacts.get(identity), entries);
      if (merged.length !== (objectFacts.get(identity)?.length ?? 0)) {
        objectFacts.set(identity, merged);
        objectChanged = true;
      }
    }
  }

  const sinkFacts = [];
  const addSink = (attributeName, fact, node) => {
    if (
      !PRESENTATION_SINK_ATTRIBUTES.has(attributeName) ||
      !fact ||
      fact.thresholdMembers.size < 2 ||
      (attributeName === "className" &&
        isLayoutOnlyClassVocabulary(fact.thresholdMembers))
    ) {
      return;
    }
    sinkFacts.push({ fact, line: lineOf(sourceFile, node) });
  };
  const discoverSinks = (node) => {
    if (
      ts.isJsxAttribute(node) &&
      node.initializer &&
      ts.isJsxExpression(node.initializer) &&
      node.initializer.expression
    ) {
      const attributeName = propertyNameText(node.name);
      if (attributeName === "style") {
        for (const entry of objectEntries(node.initializer.expression)) {
          addSink(entry.attributeName, entry.fact, node);
        }
      }
      if (attributeName) {
        addSink(
          attributeName,
          expressionFact(node.initializer.expression),
          node,
        );
      }
    }
    if (ts.isJsxSpreadAttribute(node)) {
      for (const entry of objectEntries(node.expression)) {
        addSink(entry.attributeName, entry.fact, node);
      }
    }
    ts.forEachChild(node, discoverSinks);
  };
  discoverSinks(sourceFile);

  return sinkFacts.flatMap(({ fact, line }) =>
    matching
      .filter(
        (descriptor) =>
          Array.isArray(descriptor.members) &&
          descriptor.members.length === fact.thresholdMembers.size,
      )
      .map((descriptor) => ({
        candidateId: descriptor.candidateId,
        path: relative,
        line,
      })),
  );
}

const LIFECYCLE_SINK_ATTRIBUTES = new Set(["aria-disabled", "disabled"]);
const LOGICAL_CONTROL_OPERATORS = new Set([
  ts.SyntaxKind.AmpersandAmpersandToken,
  ts.SyntaxKind.BarBarToken,
  ts.SyntaxKind.QuestionQuestionToken,
]);

function declarationPath(node) {
  return node ? relativePath(node.getSourceFile().fileName) : null;
}

function symbolDeclarationsResolveUnder(symbol, prefix) {
  const declarations = symbol?.declarations ?? [];
  return (
    declarations.length > 0 &&
    declarations.every((declaration) =>
      declarationPath(declaration)?.startsWith(prefix),
    )
  );
}

function typeRootSymbol(checker, typeNode, seen = new Set()) {
  if (!typeNode) return undefined;
  if (ts.isParenthesizedTypeNode(typeNode)) {
    return typeRootSymbol(checker, typeNode.type, seen);
  }
  if (ts.isIndexedAccessTypeNode(typeNode)) {
    return typeRootSymbol(checker, typeNode.objectType, seen);
  }
  if (ts.isTypeReferenceNode(typeNode)) {
    const symbol = symbolIdentity(checker, typeNode.typeName);
    if (!symbol || seen.has(symbol)) return symbol;
    seen.add(symbol);
    for (const declaration of symbol.declarations ?? []) {
      if (ts.isTypeAliasDeclaration(declaration)) {
        const nested = typeRootSymbol(checker, declaration.type, seen);
        if (nested) return nested;
      }
    }
    return symbol;
  }
  if (ts.isTypeQueryNode(typeNode)) {
    return symbolIdentity(checker, typeNode.exprName);
  }
  return undefined;
}

function isClosedStringLiteralType(type) {
  const members = type.isUnion?.() ? type.types : [type];
  return (
    members.length > 0 &&
    members.every((member) => (member.flags & ts.TypeFlags.StringLiteral) !== 0)
  );
}

function terminalTypeDeclarationPaths(checker, typeNode, seen = new Set()) {
  const incomplete = () => ({ paths: new Set(), complete: false });
  if (!typeNode) return incomplete();
  if (ts.isParenthesizedTypeNode(typeNode)) {
    return terminalTypeDeclarationPaths(checker, typeNode.type, seen);
  }
  if (ts.isIndexedAccessTypeNode(typeNode)) {
    return terminalTypeDeclarationPaths(checker, typeNode.objectType, seen);
  }
  if (ts.isUnionTypeNode(typeNode) || ts.isIntersectionTypeNode(typeNode)) {
    const paths = new Set();
    let complete = typeNode.types.length > 0;
    for (const member of typeNode.types) {
      const branch = terminalTypeDeclarationPaths(
        checker,
        member,
        new Set(seen),
      );
      complete = complete && branch.complete;
      for (const memberPath of branch.paths) {
        paths.add(memberPath);
      }
    }
    return { paths, complete };
  }
  if (ts.isTypeReferenceNode(typeNode)) {
    const symbol = symbolIdentity(checker, typeNode.typeName);
    if (!symbol || seen.has(symbol)) return incomplete();
    seen.add(symbol);
    const aliasDeclarations = (symbol.declarations ?? []).filter(
      (declaration) => ts.isTypeAliasDeclaration(declaration),
    );
    if (aliasDeclarations.length > 0) {
      const paths = new Set();
      let complete = true;
      for (const declaration of aliasDeclarations) {
        const branch = terminalTypeDeclarationPaths(
          checker,
          declaration.type,
          new Set(seen),
        );
        complete = complete && branch.complete;
        for (const nestedPath of branch.paths) {
          paths.add(nestedPath);
        }
      }
      return { paths, complete };
    }
    const declarations = symbol.declarations ?? [];
    const paths = new Set(
      declarations.map((declaration) => declarationPath(declaration)),
    );
    return {
      paths: new Set([...paths].filter(Boolean)),
      complete:
        declarations.length > 0 &&
        [...paths].every((declaration) => Boolean(declaration)),
    };
  }
  if (ts.isTypeQueryNode(typeNode)) {
    const symbol = symbolIdentity(checker, typeNode.exprName);
    const declarations = symbol?.declarations ?? [];
    const paths = new Set(
      declarations.map((declaration) => declarationPath(declaration)),
    );
    return {
      paths: new Set([...paths].filter(Boolean)),
      complete:
        declarations.length > 0 &&
        [...paths].every((declaration) => Boolean(declaration)),
    };
  }
  return incomplete();
}

function isGeneratedClosedInputType(checker, typeNode, governedPaths) {
  if (!isClosedStringLiteralType(checker.getTypeFromTypeNode(typeNode))) {
    return false;
  }
  if (governedPaths === undefined) {
    return symbolDeclarationsResolveUnder(
      typeRootSymbol(checker, typeNode),
      "packages/runtime-api-client/",
    );
  }
  const terminalProof = terminalTypeDeclarationPaths(checker, typeNode);
  return (
    terminalProof.complete &&
    terminalProof.paths.size > 0 &&
    [...terminalProof.paths].every((terminalPath) =>
      governedPaths.has(terminalPath),
    )
  );
}

function isAtlasBadgeToneType(checker, typeNode) {
  if (!typeNode) return false;
  const type = checker.getTypeFromTypeNode(typeNode);
  const alias = type.aliasSymbol;
  return (
    alias?.name === "BadgeTone" &&
    symbolDeclarationsResolveUnder(alias, "packages/atlas-ui/")
  );
}

function functionSymbol(checker, node) {
  if (node.name) return symbolIdentity(checker, node.name);
  const parent = node.parent;
  if (
    ts.isVariableDeclaration(parent) ||
    ts.isPropertyDeclaration(parent) ||
    ts.isPropertyAssignment(parent)
  ) {
    return symbolIdentity(checker, parent.name);
  }
  return undefined;
}

function addBindingSymbols(checker, name, target) {
  let changed = false;
  for (const identifier of bindingNames(name)) {
    const symbol = symbolIdentity(checker, identifier);
    if (symbol && !target.has(symbol)) {
      target.add(symbol);
      changed = true;
    }
  }
  return changed;
}

function sourceFunctionNodes(sourceFiles) {
  const functions = [];
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (ts.isFunctionLike(node) && node.body) functions.push(node);
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return functions;
}

function nodesInsideFunction(node) {
  const variables = [];
  const assignments = [];
  const returns = [];
  const visit = (current) => {
    if (current !== node && ts.isFunctionLike(current)) return;
    if (ts.isVariableDeclaration(current)) variables.push(current);
    if (
      ts.isBinaryExpression(current) &&
      current.operatorToken.kind === ts.SyntaxKind.EqualsToken
    ) {
      assignments.push(current);
    }
    if (ts.isReturnStatement(current) && current.expression) {
      returns.push(current);
    }
    ts.forEachChild(current, visit);
  };
  visit(node.body);
  return { assignments, returns, variables };
}

function parameterDependencies(checker, node) {
  const parameters = new Map();
  const dependentBindings = new Map();
  for (const parameter of node.parameters) {
    for (const identifier of bindingNames(parameter.name)) {
      const symbol = symbolIdentity(checker, identifier);
      if (!symbol) continue;
      parameters.set(symbol, parameter);
      dependentBindings.set(symbol, new Set([symbol]));
    }
  }
  const { assignments, variables } = nodesInsideFunction(node);
  const dependenciesOf = (expression, seen = new Set()) => {
    const current = unwrapExpression(expression);
    if (seen.has(current)) return new Set();
    seen.add(current);
    const direct = symbolIdentity(checker, current);
    const dependencies = new Set(dependentBindings.get(direct) ?? []);
    ts.forEachChild(current, (child) => {
      for (const dependency of dependenciesOf(child, seen)) {
        dependencies.add(dependency);
      }
    });
    return dependencies;
  };
  const store = (name, dependencies) => {
    let changed = false;
    if (dependencies.size === 0) return changed;
    for (const identifier of bindingNames(name)) {
      const symbol = symbolIdentity(checker, identifier);
      if (!symbol) continue;
      const current = dependentBindings.get(symbol) ?? new Set();
      const next = new Set([...current, ...dependencies]);
      if (next.size !== current.size) {
        dependentBindings.set(symbol, next);
        changed = true;
      }
    }
    return changed;
  };
  let changed = true;
  while (changed) {
    changed = false;
    for (const variable of variables) {
      if (variable.initializer) {
        changed =
          store(variable.name, dependenciesOf(variable.initializer)) || changed;
      }
    }
    for (const assignment of assignments) {
      const left = unwrapExpression(assignment.left);
      if (ts.isIdentifier(left)) {
        changed = store(left, dependenciesOf(assignment.right)) || changed;
      }
    }
  }
  return { dependenciesOf, parameters };
}

function projectionControlsInExpression(node, dependenciesOf) {
  const controls = new Set();
  const addDependencies = (expression) => {
    for (const dependency of dependenciesOf(expression)) {
      controls.add(dependency);
    }
  };
  const visit = (current) => {
    current = unwrapExpression(current);
    if (ts.isConditionalExpression(current)) {
      addDependencies(current.condition);
    }
    if (ts.isElementAccessExpression(current) && current.argumentExpression) {
      addDependencies(current.argumentExpression);
    }
    if (
      ts.isBinaryExpression(current) &&
      (LOGICAL_CONTROL_OPERATORS.has(current.operatorToken.kind) ||
        [
          ts.SyntaxKind.EqualsEqualsToken,
          ts.SyntaxKind.EqualsEqualsEqualsToken,
          ts.SyntaxKind.ExclamationEqualsToken,
          ts.SyntaxKind.ExclamationEqualsEqualsToken,
          ts.SyntaxKind.GreaterThanToken,
          ts.SyntaxKind.GreaterThanEqualsToken,
          ts.SyntaxKind.LessThanToken,
          ts.SyntaxKind.LessThanEqualsToken,
        ].includes(current.operatorToken.kind))
    ) {
      addDependencies(current.left);
      addDependencies(current.right);
    }
    if (ts.isCallExpression(current)) {
      addDependencies(current.expression);
      for (const argument of current.arguments) addDependencies(argument);
    }
    if (
      ts.isPrefixUnaryExpression(current) ||
      ts.isPostfixUnaryExpression(current)
    ) {
      addDependencies(current.operand);
    }
    ts.forEachChild(current, visit);
  };
  visit(node);
  return controls;
}

function controllingAncestors(returnNode, functionNode, dependenciesOf) {
  const controls = new Set();
  for (
    let current = returnNode.parent;
    current && current !== functionNode.body;
    current = current.parent
  ) {
    let condition;
    if (ts.isIfStatement(current)) condition = current.expression;
    if (ts.isSwitchStatement(current)) condition = current.expression;
    if (condition) {
      for (const dependency of dependenciesOf(condition)) {
        controls.add(dependency);
      }
    }
  }
  return controls;
}

function directProjectionControls(checker, node) {
  const { dependenciesOf, parameters } = parameterDependencies(checker, node);
  const controls = new Set();
  for (const returnNode of nodesInsideFunction(node).returns) {
    for (const dependency of projectionControlsInExpression(
      returnNode.expression,
      dependenciesOf,
    )) {
      controls.add(dependency);
    }
    for (const dependency of controllingAncestors(
      returnNode,
      node,
      dependenciesOf,
    )) {
      controls.add(dependency);
    }
  }
  if (node.body && !ts.isBlock(node.body)) {
    for (const dependency of projectionControlsInExpression(
      node.body,
      dependenciesOf,
    )) {
      controls.add(dependency);
    }
  }
  return {
    controls,
    parameters: [...controls]
      .map((symbol) => parameters.get(symbol))
      .filter(Boolean),
  };
}

function isAuthorizedBadgeToneProjection(
  checker,
  node,
  parameters,
  governedPaths,
) {
  return (
    parameters.length > 0 &&
    isAtlasBadgeToneType(checker, node.type) &&
    parameters.every(
      (parameter) =>
        parameter.type &&
        isGeneratedClosedInputType(checker, parameter.type, governedPaths),
    )
  );
}

function hasIndexedAccessType(checker, typeNode, seen = new Set()) {
  if (!typeNode) return false;
  if (ts.isIndexedAccessTypeNode(typeNode)) return true;
  if (ts.isTypeReferenceNode(typeNode)) {
    const symbol = symbolIdentity(checker, typeNode.typeName);
    if (symbol && !seen.has(symbol)) {
      seen.add(symbol);
      for (const declaration of symbol.declarations ?? []) {
        if (
          ts.isTypeAliasDeclaration(declaration) &&
          hasIndexedAccessType(checker, declaration.type, seen)
        ) {
          return true;
        }
      }
    }
  }
  let found = false;
  ts.forEachChild(typeNode, (child) => {
    if (!found && hasIndexedAccessType(checker, child, seen)) found = true;
  });
  return found;
}

function declaredBindingTypeNode(checker, declaration, identifier) {
  if (ts.isIdentifier(declaration.name)) return declaration.type;
  if (!ts.isObjectBindingPattern(declaration.name) || !declaration.type) {
    return declaration.type;
  }
  const element = declaration.name.elements.find((candidate) =>
    bindingNames(candidate.name).includes(identifier),
  );
  if (!element) return undefined;
  const propertyName = propertyNameText(element.propertyName ?? element.name);
  if (!propertyName) return undefined;
  const property = checker
    .getTypeFromTypeNode(declaration.type)
    .getProperty(propertyName);
  for (const propertyDeclaration of property?.declarations ?? []) {
    if (
      (ts.isPropertySignature(propertyDeclaration) ||
        ts.isPropertyDeclaration(propertyDeclaration) ||
        ts.isParameter(propertyDeclaration)) &&
      propertyDeclaration.type
    ) {
      return propertyDeclaration.type;
    }
  }
  return undefined;
}

function typeCanCarryOpenLabel(type) {
  if (
    (type.flags &
      (ts.TypeFlags.Any | ts.TypeFlags.Unknown | ts.TypeFlags.StringLike)) !==
    0
  ) {
    return true;
  }
  return Boolean(
    type.isUnion?.() &&
    type.types.some((member) => typeCanCarryOpenLabel(member)),
  );
}

function expressionStringMembers(checker, node, seen = new Set()) {
  const current = unwrapExpression(node);
  if (seen.has(current)) return new Set();
  seen.add(current);
  if (
    ts.isStringLiteral(current) ||
    ts.isNoSubstitutionTemplateLiteral(current)
  ) {
    return new Set([current.text]);
  }
  if (ts.isConditionalExpression(current)) {
    return new Set([
      ...expressionStringMembers(checker, current.whenTrue, seen),
      ...expressionStringMembers(checker, current.whenFalse, seen),
    ]);
  }
  if (ts.isCallExpression(current)) {
    const symbol = symbolIdentity(checker, current.expression);
    const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
    if (declaration && ts.isFunctionLike(declaration)) {
      return new Set(
        functionReturnExpressions(declaration).flatMap((expression) => [
          ...expressionStringMembers(checker, expression, seen),
        ]),
      );
    }
  }
  if (ts.isIdentifier(current)) {
    const symbol = symbolIdentity(checker, current);
    const declaration = symbol?.valueDeclaration;
    if (ts.isVariableDeclaration(declaration) && declaration.initializer) {
      return expressionStringMembers(checker, declaration.initializer, seen);
    }
  }
  return new Set();
}

function collectAuthoredProjectionRevivals(
  sourceFiles,
  protectedDefinitions,
  pathOf,
  checker,
  governedPaths,
) {
  const descriptors = Array.isArray(protectedDefinitions)
    ? protectedDefinitions
    : [];
  const descriptorsByPath = new Map();
  for (const descriptor of descriptors) {
    for (const protectedPath of descriptor.paths ?? []) {
      const values = descriptorsByPath.get(protectedPath) ?? [];
      values.push(descriptor);
      descriptorsByPath.set(protectedPath, values);
    }
  }

  const functions = sourceFunctionNodes(sourceFiles);
  const projectedFunctions = new Map();
  const transparentFunctions = new Map();
  const authorizedFunctions = new Set();
  const projectedValues = new Set();
  const ownerValues = new Set();
  const objectEntries = new Map();
  const variableNodes = [];
  const assignmentNodes = [];
  const parameterNodes = [];
  const objectLiteralNodes = [];
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (ts.isVariableDeclaration(node)) variableNodes.push(node);
      if (ts.isParameter(node)) parameterNodes.push(node);
      if (ts.isObjectLiteralExpression(node)) objectLiteralNodes.push(node);
      if (
        ts.isBinaryExpression(node) &&
        node.operatorToken.kind === ts.SyntaxKind.EqualsToken
      ) {
        assignmentNodes.push(node);
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  for (const node of [...parameterNodes, ...variableNodes]) {
    for (const identifier of bindingNames(node.name)) {
      const bindingType = declaredBindingTypeNode(checker, node, identifier);
      if (!hasIndexedAccessType(checker, bindingType)) continue;
      if (!typeCanCarryOpenLabel(checker.getTypeAtLocation(identifier))) {
        continue;
      }
      const symbol = symbolIdentity(checker, identifier);
      if (symbol) ownerValues.add(symbol);
    }
  }

  const expressionIsOwnerDerived = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return false;
    seen.add(current);
    const symbol = symbolIdentity(checker, current);
    if (symbol && ownerValues.has(symbol)) return true;
    if (ts.isPropertyAccessExpression(current)) {
      if (
        symbolDeclarationsResolveUnder(
          symbolIdentity(checker, current.name),
          "packages/runtime-api-client/",
        ) &&
        typeCanCarryOpenLabel(checker.getTypeAtLocation(current))
      ) {
        return true;
      }
      return expressionIsOwnerDerived(current.expression, seen);
    }
    if (ts.isElementAccessExpression(current)) {
      return (
        expressionIsOwnerDerived(current.expression, seen) ||
        Boolean(
          current.argumentExpression &&
          expressionIsOwnerDerived(current.argumentExpression, seen),
        )
      );
    }
    if (ts.isConditionalExpression(current)) {
      return (
        expressionIsOwnerDerived(current.condition, seen) ||
        expressionIsOwnerDerived(current.whenTrue, seen) ||
        expressionIsOwnerDerived(current.whenFalse, seen)
      );
    }
    if (ts.isBinaryExpression(current)) {
      return (
        expressionIsOwnerDerived(current.left, seen) ||
        expressionIsOwnerDerived(current.right, seen)
      );
    }
    if (
      ts.isPrefixUnaryExpression(current) ||
      ts.isPostfixUnaryExpression(current)
    ) {
      return expressionIsOwnerDerived(current.operand, seen);
    }
    if (
      ts.isAwaitExpression(current) ||
      ts.isYieldExpression(current) ||
      ts.isSpreadElement(current)
    ) {
      return Boolean(
        current.expression &&
        expressionIsOwnerDerived(current.expression, seen),
      );
    }
    if (ts.isArrayLiteralExpression(current)) {
      return current.elements.some((element) =>
        expressionIsOwnerDerived(element, seen),
      );
    }
    if (ts.isObjectLiteralExpression(current)) {
      return current.properties.some((property) => {
        if (ts.isPropertyAssignment(property)) {
          return expressionIsOwnerDerived(property.initializer, seen);
        }
        if (ts.isShorthandPropertyAssignment(property)) {
          return expressionIsOwnerDerived(property.name, seen);
        }
        if (ts.isSpreadAssignment(property)) {
          return expressionIsOwnerDerived(property.expression, seen);
        }
        return false;
      });
    }
    return false;
  };

  let ownerChanged = true;
  while (ownerChanged) {
    ownerChanged = false;
    for (const node of variableNodes) {
      if (node.initializer && expressionIsOwnerDerived(node.initializer)) {
        ownerChanged =
          addBindingSymbols(checker, node.name, ownerValues) || ownerChanged;
      }
    }
    for (const node of assignmentNodes) {
      const left = unwrapExpression(node.left);
      if (ts.isIdentifier(left) && expressionIsOwnerDerived(node.right)) {
        ownerChanged =
          addBindingSymbols(checker, left, ownerValues) || ownerChanged;
      }
      const property = objectPropertyTarget(left);
      if (
        property?.object &&
        expressionIsOwnerDerived(node.right) &&
        !ownerValues.has(property.object)
      ) {
        ownerValues.add(property.object);
        ownerChanged = true;
      }
    }
  }

  for (const node of functions) {
    const symbol = functionSymbol(checker, node);
    if (!symbol) continue;
    const parameterSymbols = node.parameters.map((parameter) => {
      const names = bindingNames(parameter.name);
      return names.length === 1 ? symbolIdentity(checker, names[0]) : undefined;
    });
    const returned = functionReturnExpressions(node).map((expression) =>
      unwrapExpression(expression),
    );
    if (returned.length > 0) {
      const index = parameterSymbols.findIndex(
        (parameterSymbol) =>
          parameterSymbol &&
          returned.every(
            (expression) =>
              ts.isIdentifier(expression) &&
              symbolIdentity(checker, expression) === parameterSymbol,
          ),
      );
      if (index >= 0) transparentFunctions.set(symbol, new Set([index]));
    }
    const { controls, parameters } = directProjectionControls(checker, node);
    const authorized =
      controls.size > 0 &&
      isAuthorizedBadgeToneProjection(checker, node, parameters, governedPaths);
    if (authorized) authorizedFunctions.add(symbol);
    if (controls.size > 0 && !authorized) {
      projectedFunctions.set(
        symbol,
        new Set(
          parameters
            .map((parameter) => node.parameters.indexOf(parameter))
            .filter((index) => index >= 0),
        ),
      );
    }
  }

  const copyFunctionSummarySymbols = (target, source) => {
    if (!target || !source || target === source) return false;
    if (authorizedFunctions.has(source) && !authorizedFunctions.has(target)) {
      authorizedFunctions.add(target);
      return true;
    }
    for (const summaries of [projectedFunctions, transparentFunctions]) {
      const sourceSummary = summaries.get(source);
      if (sourceSummary && !summaries.has(target)) {
        summaries.set(target, new Set(sourceSummary));
        return true;
      }
    }
    return false;
  };
  const copyFunctionSummary = (targetNode, sourceNode) =>
    copyFunctionSummarySymbols(
      symbolIdentity(checker, targetNode),
      symbolIdentity(checker, unwrapExpression(sourceNode)),
    );
  const stableBindingKey = (node) => {
    const symbol = symbolIdentity(checker, unwrapExpression(node));
    const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
    return declaration
      ? `${declaration.getSourceFile().fileName}:${declaration.pos}:${declaration.end}:${symbol.name}`
      : undefined;
  };
  const objectFunctionSources = new Map();
  const propertySourceRelations = [];
  const spreadSourceRelations = [];
  const objectAliasRelations = [];
  const propertyReference = (node) => {
    const current = unwrapExpression(node);
    if (ts.isPropertyAccessExpression(current)) {
      return {
        name: current.name.text,
        object: stableBindingKey(current.expression),
      };
    }
    if (
      ts.isElementAccessExpression(current) &&
      current.argumentExpression &&
      (ts.isStringLiteral(current.argumentExpression) ||
        ts.isNoSubstitutionTemplateLiteral(current.argumentExpression))
    ) {
      return {
        name: current.argumentExpression.text,
        object: stableBindingKey(current.expression),
      };
    }
    return null;
  };
  const objectLiteralOwner = (objectLiteral) => {
    let current = objectLiteral;
    while (
      current.parent &&
      (ts.isParenthesizedExpression(current.parent) ||
        ts.isAsExpression(current.parent) ||
        ts.isSatisfiesExpression(current.parent))
    ) {
      current = current.parent;
    }
    return ts.isVariableDeclaration(current.parent) &&
      current.parent.initializer === current &&
      ts.isIdentifier(current.parent.name)
      ? stableBindingKey(current.parent.name)
      : undefined;
  };
  for (const objectLiteral of objectLiteralNodes) {
    const target = objectLiteralOwner(objectLiteral);
    if (!target) continue;
    for (const property of objectLiteral.properties) {
      if (ts.isShorthandPropertyAssignment(property)) {
        propertySourceRelations.push({
          name: property.name.text,
          sourceSymbol: checker.getShorthandAssignmentValueSymbol(property),
          target,
        });
      }
      if (ts.isPropertyAssignment(property)) {
        const name = propertyNameText(property.name);
        if (name) {
          propertySourceRelations.push({
            name,
            sourceExpression: property.initializer,
            target,
          });
        }
      }
      if (ts.isSpreadAssignment(property)) {
        spreadSourceRelations.push({
          source: stableBindingKey(property.expression),
          target,
        });
      }
    }
  }
  for (const variable of variableNodes) {
    if (!variable.initializer || !ts.isIdentifier(variable.name)) continue;
    objectAliasRelations.push({
      source: stableBindingKey(variable.initializer),
      target: stableBindingKey(variable.name),
    });
  }
  for (const assignment of assignmentNodes) {
    const left = unwrapExpression(assignment.left);
    const property = propertyReference(left);
    if (property?.object) {
      propertySourceRelations.push({
        name: property.name,
        sourceExpression: assignment.right,
        target: property.object,
      });
    }
  }
  const sourceFunctionSymbol = (node) => {
    const property = propertyReference(node);
    if (property?.object) {
      const source = objectFunctionSources
        .get(property.object)
        ?.get(property.name);
      if (source) return source;
    }
    return symbolIdentity(checker, unwrapExpression(node));
  };
  const setObjectFunctionSource = (target, name, source) => {
    if (!target || !source) return false;
    const entries = objectFunctionSources.get(target) ?? new Map();
    if (entries.has(name)) return false;
    entries.set(name, source);
    objectFunctionSources.set(target, entries);
    return true;
  };
  let objectSourceChanged = true;
  while (objectSourceChanged) {
    objectSourceChanged = false;
    for (const relation of propertySourceRelations) {
      objectSourceChanged =
        setObjectFunctionSource(
          relation.target,
          relation.name,
          relation.sourceSymbol ??
            sourceFunctionSymbol(relation.sourceExpression),
        ) || objectSourceChanged;
    }
    for (const relation of [
      ...spreadSourceRelations,
      ...objectAliasRelations,
    ]) {
      for (const [name, source] of objectFunctionSources.get(relation.source) ??
        []) {
        objectSourceChanged =
          setObjectFunctionSource(relation.target, name, source) ||
          objectSourceChanged;
      }
    }
  }
  let functionAliasChanged = true;
  while (functionAliasChanged) {
    functionAliasChanged = false;
    for (const node of variableNodes) {
      if (!node.initializer || !ts.isIdentifier(node.name)) continue;
      functionAliasChanged =
        copyFunctionSummary(node.name, node.initializer) ||
        functionAliasChanged;
    }
    for (const node of assignmentNodes) {
      const left = unwrapExpression(node.left);
      if (!ts.isIdentifier(left)) continue;
      functionAliasChanged =
        copyFunctionSummary(left, node.right) || functionAliasChanged;
    }
  }

  const hasOwnerControlledProjection = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return false;
    seen.add(current);
    if (
      ts.isConditionalExpression(current) &&
      expressionIsOwnerDerived(current.condition)
    ) {
      return true;
    }
    if (
      ts.isElementAccessExpression(current) &&
      current.argumentExpression &&
      expressionIsOwnerDerived(current.argumentExpression)
    ) {
      return true;
    }
    if (
      ts.isBinaryExpression(current) &&
      (LOGICAL_CONTROL_OPERATORS.has(current.operatorToken.kind) ||
        [
          ts.SyntaxKind.EqualsEqualsToken,
          ts.SyntaxKind.EqualsEqualsEqualsToken,
          ts.SyntaxKind.ExclamationEqualsToken,
          ts.SyntaxKind.ExclamationEqualsEqualsToken,
          ts.SyntaxKind.GreaterThanToken,
          ts.SyntaxKind.GreaterThanEqualsToken,
          ts.SyntaxKind.LessThanToken,
          ts.SyntaxKind.LessThanEqualsToken,
        ].includes(current.operatorToken.kind)) &&
      (expressionIsOwnerDerived(current.left) ||
        expressionIsOwnerDerived(current.right))
    ) {
      return true;
    }
    if (
      (ts.isPrefixUnaryExpression(current) ||
        ts.isPostfixUnaryExpression(current)) &&
      expressionIsOwnerDerived(current.operand)
    ) {
      return true;
    }
    if (
      ts.isCallExpression(current) &&
      !symbolIdentity(checker, current.expression) &&
      (expressionIsOwnerDerived(current.expression) ||
        current.arguments.some((argument) =>
          expressionIsOwnerDerived(argument),
        ))
    ) {
      return true;
    }
    let found = false;
    ts.forEachChild(current, (child) => {
      if (!found && hasOwnerControlledProjection(child, seen)) found = true;
    });
    return found;
  };

  function objectPropertyTarget(node) {
    const current = unwrapExpression(node);
    if (ts.isPropertyAccessExpression(current)) {
      return {
        name: current.name.text,
        object: symbolIdentity(checker, current.expression),
      };
    }
    if (
      ts.isElementAccessExpression(current) &&
      current.argumentExpression &&
      (ts.isStringLiteral(current.argumentExpression) ||
        ts.isNoSubstitutionTemplateLiteral(current.argumentExpression))
    ) {
      return {
        name: current.argumentExpression.text,
        object: symbolIdentity(checker, current.expression),
      };
    }
    return null;
  }

  const expressionIsProjected = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return false;
    seen.add(current);
    const symbol = symbolIdentity(checker, current);
    if (symbol && projectedValues.has(symbol)) return true;
    if (hasOwnerControlledProjection(current)) return true;
    if (ts.isCallExpression(current)) {
      const callee = sourceFunctionSymbol(current.expression);
      let controls =
        projectedFunctions.get(callee) ?? transparentFunctions.get(callee);
      if (
        !controls &&
        callee &&
        ["Boolean", "Number", "String"].includes(callee.name) &&
        (callee.declarations ?? []).length > 0 &&
        (callee.declarations ?? []).every((declaration) =>
          /\/typescript\/lib\/lib\.[^/]+\.d\.ts$/u.test(
            declaration.getSourceFile().fileName,
          ),
        )
      ) {
        controls = new Set([0]);
      }
      if (!controls) return false;
      if (controls.has(-1)) return true;
      return [...controls].some((index) => {
        const argument = current.arguments[index];
        return Boolean(
          argument &&
          (expressionIsOwnerDerived(argument) ||
            expressionIsProjected(argument, seen)),
        );
      });
    }
    if (
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      const property = objectPropertyTarget(current);
      if (
        property?.object &&
        objectEntries.get(property.object)?.has(property.name)
      ) {
        return true;
      }
      return (
        expressionIsProjected(current.expression, seen) ||
        (ts.isElementAccessExpression(current) &&
          Boolean(
            current.argumentExpression &&
            expressionIsProjected(current.argumentExpression, seen),
          ))
      );
    }
    if (ts.isConditionalExpression(current)) {
      return (
        expressionIsProjected(current.condition, seen) ||
        expressionIsProjected(current.whenTrue, seen) ||
        expressionIsProjected(current.whenFalse, seen)
      );
    }
    if (ts.isBinaryExpression(current)) {
      return (
        expressionIsProjected(current.left, seen) ||
        expressionIsProjected(current.right, seen)
      );
    }
    if (
      ts.isPrefixUnaryExpression(current) ||
      ts.isPostfixUnaryExpression(current)
    ) {
      return expressionIsProjected(current.operand, seen);
    }
    if (
      ts.isAwaitExpression(current) ||
      ts.isYieldExpression(current) ||
      ts.isSpreadElement(current)
    ) {
      return Boolean(
        current.expression && expressionIsProjected(current.expression, seen),
      );
    }
    if (ts.isArrayLiteralExpression(current)) {
      return current.elements.some((element) =>
        expressionIsProjected(element, seen),
      );
    }
    if (ts.isObjectLiteralExpression(current)) {
      return current.properties.some((property) => {
        if (ts.isPropertyAssignment(property)) {
          return expressionIsProjected(property.initializer, seen);
        }
        if (ts.isShorthandPropertyAssignment(property)) {
          return expressionIsProjected(property.name, seen);
        }
        if (ts.isSpreadAssignment(property)) {
          return expressionIsProjected(property.expression, seen);
        }
        return false;
      });
    }
    return false;
  };

  const projectedObjectEntries = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return new Set();
    seen.add(current);
    if (
      ts.isIdentifier(current) ||
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      return new Set(objectEntries.get(symbolIdentity(checker, current)) ?? []);
    }
    if (!ts.isObjectLiteralExpression(current)) return new Set();
    const entries = new Set();
    for (const property of current.properties) {
      if (ts.isSpreadAssignment(property)) {
        for (const entry of projectedObjectEntries(property.expression, seen)) {
          entries.add(entry);
        }
      }
      if (
        ts.isPropertyAssignment(property) &&
        (expressionIsProjected(property.initializer) ||
          expressionIsOwnerDerived(property.initializer))
      ) {
        const name = propertyNameText(property.name);
        if (name) entries.add(name);
      }
      if (
        ts.isShorthandPropertyAssignment(property) &&
        (expressionIsProjected(property.name) ||
          expressionIsOwnerDerived(property.name))
      ) {
        entries.add(property.name.text);
      }
    }
    return entries;
  };

  let changed = true;
  while (changed) {
    changed = false;
    for (const node of variableNodes) {
      if (!node.initializer) continue;
      if (expressionIsProjected(node.initializer)) {
        changed =
          addBindingSymbols(checker, node.name, projectedValues) || changed;
      }
      const entries = projectedObjectEntries(node.initializer);
      for (const identifier of bindingNames(node.name)) {
        const symbol = symbolIdentity(checker, identifier);
        if (!symbol || entries.size === 0) continue;
        const current = objectEntries.get(symbol) ?? new Set();
        const next = new Set([...current, ...entries]);
        if (next.size !== current.size) {
          objectEntries.set(symbol, next);
          changed = true;
        }
      }
    }
    for (const node of assignmentNodes) {
      const left = unwrapExpression(node.left);
      if (ts.isIdentifier(left) && expressionIsProjected(node.right)) {
        changed = addBindingSymbols(checker, left, projectedValues) || changed;
      }
      if (ts.isIdentifier(left)) {
        const symbol = symbolIdentity(checker, left);
        const entries = projectedObjectEntries(node.right);
        if (symbol && entries.size > 0) {
          const current = objectEntries.get(symbol) ?? new Set();
          const next = new Set([...current, ...entries]);
          if (next.size !== current.size) {
            objectEntries.set(symbol, next);
            changed = true;
          }
        }
      }
      const property = objectPropertyTarget(left);
      if (
        property?.object &&
        (expressionIsProjected(node.right) ||
          expressionIsOwnerDerived(node.right))
      ) {
        const current = objectEntries.get(property.object) ?? new Set();
        if (!current.has(property.name)) {
          objectEntries.set(
            property.object,
            new Set([...current, property.name]),
          );
          changed = true;
        }
      }
    }
    for (const node of functions) {
      const symbol = functionSymbol(checker, node);
      if (
        symbol &&
        !authorizedFunctions.has(symbol) &&
        !projectedFunctions.has(symbol) &&
        functionReturnExpressions(node).some((expression) =>
          expressionIsProjected(expression),
        )
      ) {
        projectedFunctions.set(symbol, new Set([-1]));
        changed = true;
      }
    }
  }

  const revivals = [];
  const addRevival = (sourceFile, node) => {
    const relative = pathOf(sourceFile);
    for (const descriptor of descriptorsByPath.get(relative) ?? []) {
      revivals.push({
        candidateId: descriptor.candidateId,
        path: relative,
        line: lineOf(sourceFile, node),
      });
    }
  };
  const projectedPresentationSink = (attributeName, expression) => {
    if (!PRESENTATION_SINK_ATTRIBUTES.has(attributeName)) return false;
    if (
      !expressionIsProjected(expression) &&
      !expressionIsOwnerDerived(expression)
    ) {
      return false;
    }
    if (attributeName !== "className") return true;
    const members = expressionStringMembers(checker, expression);
    return members.size === 0 || !isLayoutOnlyClassVocabulary(members);
  };
  const containsJsx = (node) => {
    let found = false;
    const visit = (current) => {
      if (
        ts.isJsxElement(current) ||
        ts.isJsxSelfClosingElement(current) ||
        ts.isJsxFragment(current)
      ) {
        found = true;
        return;
      }
      ts.forEachChild(current, visit);
    };
    visit(node);
    return found;
  };
  const isNonStringScalar = (node) => {
    const type = checker.getTypeAtLocation(node);
    const members = type.isUnion?.() ? type.types : [type];
    const scalarFlags =
      ts.TypeFlags.BooleanLike |
      ts.TypeFlags.NumberLike |
      ts.TypeFlags.BigIntLike |
      ts.TypeFlags.Null |
      ts.TypeFlags.Undefined;
    return (
      members.length > 0 &&
      members.every((member) => (member.flags & scalarFlags) !== 0)
    );
  };
  const isReturnedValue = (node) => {
    let current = node;
    while (
      current.parent &&
      (ts.isParenthesizedExpression(current.parent) ||
        ts.isAsExpression(current.parent) ||
        ts.isTypeAssertionExpression(current.parent) ||
        ts.isNonNullExpression(current.parent) ||
        ts.isSatisfiesExpression(current.parent))
    ) {
      current = current.parent;
    }
    return (
      ts.isReturnStatement(current.parent) ||
      (ts.isFunctionLike(current.parent) && current.parent.body === current)
    );
  };
  const controlledSubtreeHasLifecycleEffect = (node) => {
    let found = false;
    const visit = (current) => {
      if (current !== node && ts.isFunctionLike(current)) return;
      if (
        ts.isJsxElement(current) ||
        ts.isJsxSelfClosingElement(current) ||
        ts.isJsxFragment(current) ||
        ts.isThrowStatement(current) ||
        ts.isBreakStatement(current) ||
        ts.isContinueStatement(current) ||
        ((ts.isPrefixUnaryExpression(current) ||
          ts.isPostfixUnaryExpression(current)) &&
          [ts.SyntaxKind.PlusPlusToken, ts.SyntaxKind.MinusMinusToken].includes(
            current.operator,
          )) ||
        (ts.isReturnStatement(current) &&
          current.expression &&
          (containsJsx(current.expression) ||
            isNonStringScalar(current.expression)))
      ) {
        found = true;
        return;
      }
      ts.forEachChild(current, visit);
    };
    visit(node);
    return found;
  };
  const branchControlIsLifecycle = (node) => {
    if (ts.isConditionalExpression(node)) {
      return (
        containsJsx(node.whenTrue) ||
        containsJsx(node.whenFalse) ||
        (isReturnedValue(node) &&
          isNonStringScalar(node.whenTrue) &&
          isNonStringScalar(node.whenFalse) &&
          node.whenTrue.getText(node.getSourceFile()) !==
            node.whenFalse.getText(node.getSourceFile()))
      );
    }
    if (ts.isIfStatement(node)) {
      return (
        controlledSubtreeHasLifecycleEffect(node.thenStatement) ||
        Boolean(
          node.elseStatement &&
          controlledSubtreeHasLifecycleEffect(node.elseStatement),
        )
      );
    }
    if (ts.isSwitchStatement(node)) {
      return controlledSubtreeHasLifecycleEffect(node);
    }
    return true;
  };

  for (const sourceFile of sourceFiles) {
    if (!descriptorsByPath.has(pathOf(sourceFile))) continue;
    const visit = (node) => {
      if (
        ts.isJsxAttribute(node) &&
        node.initializer &&
        ts.isJsxExpression(node.initializer) &&
        node.initializer.expression
      ) {
        const attributeName = propertyNameText(node.name);
        if (
          attributeName &&
          (projectedPresentationSink(
            attributeName,
            node.initializer.expression,
          ) ||
            (LIFECYCLE_SINK_ATTRIBUTES.has(attributeName) &&
              (expressionIsProjected(node.initializer.expression) ||
                expressionIsOwnerDerived(node.initializer.expression))))
        ) {
          addRevival(sourceFile, node);
        }
      }
      if (ts.isJsxSpreadAttribute(node)) {
        const entries = projectedObjectEntries(node.expression);
        if (
          expressionIsProjected(node.expression) ||
          [...entries].some(
            (entry) =>
              PRESENTATION_SINK_ATTRIBUTES.has(entry) ||
              LIFECYCLE_SINK_ATTRIBUTES.has(entry),
          )
        ) {
          addRevival(sourceFile, node);
        }
      }
      if (
        ((ts.isIfStatement(node) || ts.isSwitchStatement(node)) &&
          expressionIsProjected(node.expression) &&
          branchControlIsLifecycle(node)) ||
        ((ts.isWhileStatement(node) || ts.isDoStatement(node)) &&
          expressionIsProjected(node.expression)) ||
        (ts.isForStatement(node) &&
          node.condition &&
          expressionIsProjected(node.condition)) ||
        (ts.isConditionalExpression(node) &&
          expressionIsProjected(node.condition) &&
          branchControlIsLifecycle(node))
      ) {
        addRevival(sourceFile, node);
      }
      if (
        ts.isBinaryExpression(node) &&
        LOGICAL_CONTROL_OPERATORS.has(node.operatorToken.kind) &&
        expressionIsProjected(node.left) &&
        (ts.isJsxElement(unwrapExpression(node.right)) ||
          ts.isJsxSelfClosingElement(unwrapExpression(node.right)) ||
          (isReturnedValue(node) && isNonStringScalar(node.right)))
      ) {
        addRevival(sourceFile, node);
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return revivals;
}

function collectProtectedRevivals(
  sourceFiles,
  protectedDefinitions,
  pathOf,
  checker,
  governedPaths,
) {
  const descriptors = Array.isArray(protectedDefinitions)
    ? protectedDefinitions
    : [];
  const revivals = new Map();
  for (const fact of collectAuthoredProjectionRevivals(
    sourceFiles,
    descriptors,
    pathOf,
    checker,
    governedPaths,
  )) {
    revivals.set(`${fact.candidateId}:${fact.path}:${fact.line}`, fact);
  }
  for (const sourceFile of sourceFiles) {
    const relative = pathOf(sourceFile);
    const matching = descriptors.filter(
      (descriptor) =>
        Array.isArray(descriptor.paths) && descriptor.paths.includes(relative),
    );
    if (matching.length === 0) continue;
    for (const fact of collectThresholdPresentationRevivals(
      sourceFile,
      matching,
      relative,
      checker,
    )) {
      revivals.set(`${fact.candidateId}:${fact.path}:${fact.line}`, fact);
    }
    const visit = (node) => {
      const members = genericVocabularyMembers(node, sourceFile);
      if (members) {
        for (const descriptor of matching) {
          const expected = Array.isArray(descriptor.members)
            ? [...descriptor.members].sort()
            : [];
          if (
            members.length === expected.length &&
            members.every((member, index) => member === expected[index])
          ) {
            const fact = {
              candidateId: descriptor.candidateId,
              path: relative,
              line: lineOf(sourceFile, node),
            };
            revivals.set(`${fact.candidateId}:${fact.path}:${fact.line}`, fact);
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return [...revivals.values()].sort((left, right) =>
    `${left.candidateId}:${left.path}:${left.line}`.localeCompare(
      `${right.candidateId}:${right.path}:${right.line}`,
    ),
  );
}

function collectInteractionLeaks(sourceFiles, identities) {
  const taintedValues = new Set();
  const taintedFunctions = new Set();

  const expressionUsesTaintedFunction = (node) => {
    const current = unwrapExpression(node);
    if (ts.isIdentifier(current) || ts.isPropertyAccessExpression(current)) {
      const identity = identities.binding(current);
      return identity !== undefined && taintedFunctions.has(identity);
    }
    return false;
  };

  const expressionIsTainted = (node, seen = new Set()) => {
    const current = unwrapExpression(node);
    if (seen.has(current)) return false;
    seen.add(current);
    const identity = identities.binding(current);
    if (identity !== undefined && taintedValues.has(identity)) return true;
    if (ts.isCallExpression(current)) {
      if (identities.isFactory(current.expression)) return true;
      const callee = identities.binding(current.expression);
      if (callee !== undefined && taintedFunctions.has(callee)) return true;
      return current.arguments.some((argument) =>
        expressionIsTainted(argument, seen),
      );
    }
    if (
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      return expressionIsTainted(current.expression, seen);
    }
    if (ts.isConditionalExpression(current)) {
      return (
        expressionIsTainted(current.whenTrue, seen) ||
        expressionIsTainted(current.whenFalse, seen)
      );
    }
    if (ts.isBinaryExpression(current)) {
      return (
        expressionIsTainted(current.left, seen) ||
        expressionIsTainted(current.right, seen)
      );
    }
    if (ts.isArrayLiteralExpression(current)) {
      return current.elements.some((element) =>
        expressionIsTainted(element, seen),
      );
    }
    if (ts.isObjectLiteralExpression(current)) {
      return current.properties.some((property) => {
        if (ts.isPropertyAssignment(property)) {
          return expressionIsTainted(property.initializer, seen);
        }
        if (ts.isShorthandPropertyAssignment(property)) {
          return expressionIsTainted(property.name, seen);
        }
        if (ts.isSpreadAssignment(property)) {
          return expressionIsTainted(property.expression, seen);
        }
        return false;
      });
    }
    if (ts.isTemplateExpression(current)) {
      return current.templateSpans.some((span) =>
        expressionIsTainted(span.expression, seen),
      );
    }
    if (
      ts.isAwaitExpression(current) ||
      ts.isYieldExpression(current) ||
      ts.isSpreadElement(current)
    ) {
      return Boolean(
        current.expression && expressionIsTainted(current.expression, seen),
      );
    }
    return false;
  };

  const addBindings = (name, target) => {
    let changed = false;
    for (const identifier of bindingNames(name)) {
      const identity = identities.binding(identifier);
      if (identity !== undefined && !target.has(identity)) {
        target.add(identity);
        changed = true;
      }
    }
    return changed;
  };

  let changed = true;
  while (changed) {
    changed = false;
    for (const sourceFile of sourceFiles) {
      const visit = (node) => {
        if (ts.isVariableDeclaration(node) && node.initializer) {
          if (
            ts.isArrowFunction(node.initializer) ||
            ts.isFunctionExpression(node.initializer)
          ) {
            if (
              functionReturnExpressions(node.initializer).some((expression) =>
                expressionIsTainted(expression),
              )
            ) {
              changed = addBindings(node.name, taintedFunctions) || changed;
            }
          } else {
            if (expressionIsTainted(node.initializer)) {
              changed = addBindings(node.name, taintedValues) || changed;
            }
            if (expressionUsesTaintedFunction(node.initializer)) {
              changed = addBindings(node.name, taintedFunctions) || changed;
            }
          }
        }
        if (
          ts.isFunctionLike(node) &&
          node.name &&
          functionReturnExpressions(node).some((expression) =>
            expressionIsTainted(expression),
          )
        ) {
          changed = addBindings(node.name, taintedFunctions) || changed;
        }
        if (
          ts.isBinaryExpression(node) &&
          node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
          expressionIsTainted(node.right)
        ) {
          const left = unwrapExpression(node.left);
          if (ts.isIdentifier(left)) {
            changed = addBindings(left, taintedValues) || changed;
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(sourceFile);
    }
  }

  const leaks = [];
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (
        ts.isCallExpression(node) &&
        identities.isSink(node.expression) &&
        node.arguments.some((argument) => expressionIsTainted(argument))
      ) {
        leaks.push({
          path: identities.path(sourceFile),
          line: lineOf(sourceFile, node),
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return leaks;
}

function consumerKind(sourceFile, node) {
  const relative = relativePath(sourceFile.fileName);
  if (/\.stories\.[cm]?tsx?$/.test(relative)) return "story";
  if (/\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$/.test(relative)) return "test";
  if (/fixture/iu.test(relative)) return "fixture";
  for (
    let current = node.parent;
    current && current !== sourceFile;
    current = current.parent
  ) {
    if (ts.isImportDeclaration(current) || ts.isExportDeclaration(current))
      return "import";
    if (
      ts.isCallExpression(current) &&
      /(?:useState|createSignal)/u.test(current.expression.getText(sourceFile))
    ) {
      return "state_initializer";
    }
    if (
      ts.isBinaryExpression(current) ||
      ts.isSwitchStatement(current) ||
      ts.isCaseClause(current)
    ) {
      return "comparison";
    }
    if (ts.isObjectLiteralExpression(current)) return "map";
    if (
      ts.isJsxAttribute(current) ||
      ts.isPropertyAssignment(current) ||
      ts.isPropertyAccessExpression(current)
    ) {
      return "prop";
    }
  }
  return "prop";
}

function symbolIdentity(checker, node) {
  let symbol = checker.getSymbolAtLocation(node);
  if (symbol && (symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    symbol = checker.getAliasedSymbol(symbol);
  }
  return symbol;
}

function atlasComponentDeclaration(checker, tagName) {
  const symbol = symbolIdentity(checker, tagName);
  return (symbol?.declarations ?? []).find((declaration) =>
    declarationPath(declaration)?.startsWith("packages/atlas-ui/src/"),
  );
}

function componentPropsType(checker, tagName) {
  const tagType = checker.getTypeAtLocation(tagName);
  for (const signature of checker.getSignaturesOfType(
    tagType,
    ts.SignatureKind.Call,
  )) {
    const parameter = signature.getParameters()[0];
    if (parameter) return checker.getTypeOfSymbolAtLocation(parameter, tagName);
  }
  return null;
}

function typeHasProperty(checker, type, field, seen = new Set()) {
  if (!type || seen.has(type)) return false;
  seen.add(type);
  if (checker.getPropertyOfType(type, field)) return true;
  return (type.types ?? []).some((member) =>
    typeHasProperty(checker, member, field, seen),
  );
}

function atlasSinkDeclaration(checker, tagName, prop) {
  const declaration = atlasComponentDeclaration(checker, tagName);
  if (!declaration) return null;
  const componentDeclarationPath = declarationPath(declaration);
  if (
    prop === "presentation" &&
    componentDeclarationPath ===
      "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
  ) {
    return componentDeclarationPath;
  }
  if (!LIFECYCLE_SINK_ATTRIBUTES.has(prop)) return null;
  const propsType = componentPropsType(checker, tagName);
  return typeHasProperty(checker, propsType, prop)
    ? componentDeclarationPath
    : null;
}

function collectAuthoritySinkDeclarations(sourceFiles, checker, pathOf) {
  const declarations = new Map();
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        for (const prop of ["presentation", ...LIFECYCLE_SINK_ATTRIBUTES]) {
          const hasAttribute = node.attributes.properties.some(
            (attribute) =>
              ts.isJsxAttribute(attribute) && attribute.name.text === prop,
          );
          if (!hasAttribute) continue;
          const componentDeclarationPath = atlasSinkDeclaration(
            checker,
            node.tagName,
            prop,
          );
          if (!componentDeclarationPath) continue;
          const key = `${componentDeclarationPath}:${prop}`;
          if (!declarations.has(key)) {
            declarations.set(key, {
              componentDeclarationPath,
              prop,
              observedAt: {
                path: pathOf(sourceFile),
                line: lineOf(sourceFile, node),
              },
            });
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return [...declarations.values()].sort((left, right) =>
    `${left.componentDeclarationPath}:${left.prop}`.localeCompare(
      `${right.componentDeclarationPath}:${right.prop}`,
    ),
  );
}

function jsxOpening(node) {
  if (ts.isJsxElement(node)) return node.openingElement;
  return ts.isJsxSelfClosingElement(node) ? node : null;
}

function componentDeclarationIdentity(checker, tagName) {
  const symbol = symbolIdentity(checker, tagName);
  const declarations = (symbol?.declarations ?? [])
    .map((declaration) => ({
      declaration,
      path: declarationPath(declaration),
      line: lineOf(declaration.getSourceFile(), declaration),
      declarationSha256: textSha256(
        declaration.getText(declaration.getSourceFile()),
      ),
    }))
    .filter(({ path: candidatePath }) => Boolean(candidatePath));
  return {
    component: String(symbol?.name ?? tagName.getText()),
    declarations,
  };
}

function siteReceipt(sourceFile, node, pathOf) {
  return {
    path: pathOf(sourceFile),
    line: lineOf(sourceFile, node),
    siteSha256: textSha256(node.getText(sourceFile)),
  };
}

function collectDirectBadgeSites(sourceFiles, checker, pathOf) {
  const sites = [];
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      const opening = jsxOpening(node);
      if (opening) {
        const identity = componentDeclarationIdentity(checker, opening.tagName);
        const badgeDeclaration = identity.declarations.find(
          ({ path: candidatePath }) =>
            candidatePath === "packages/atlas-ui/src/primitives/Badge.tsx",
        );
        if (badgeDeclaration) {
          sites.push({
            ...siteReceipt(sourceFile, node, pathOf),
            component: identity.component,
            componentDeclarationPath: badgeDeclaration.path,
            componentDeclarationLine: badgeDeclaration.line,
            componentDeclarationSha256: badgeDeclaration.declarationSha256,
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return sites.sort((left, right) =>
    `${left.path}:${String(left.line).padStart(8, "0")}:${left.siteSha256}`.localeCompare(
      `${right.path}:${String(right.line).padStart(8, "0")}:${right.siteSha256}`,
    ),
  );
}

function collectAuthorityPropCensus(sourceFiles, checker, pathOf, descriptors) {
  const requested = new Map(
    (Array.isArray(descriptors) ? descriptors : []).map((descriptor) => [
      `${descriptor.component}:${descriptor.componentDeclarationPath}:${descriptor.prop}`,
      descriptor,
    ]),
  );
  const facts = new Map();
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      const opening = jsxOpening(node);
      if (!opening) {
        ts.forEachChild(node, visit);
        return;
      }
      const identity = componentDeclarationIdentity(checker, opening.tagName);
      for (const {
        declaration,
        path: componentDeclarationPath,
      } of identity.declarations) {
        const descriptorEntries = [...requested.entries()].filter(
          ([, descriptor]) =>
            descriptor.component === identity.component &&
            descriptor.componentDeclarationPath === componentDeclarationPath,
        );
        if (descriptorEntries.length === 0) continue;
        const propsType = componentPropsType(checker, opening.tagName);
        for (const [key, descriptor] of descriptorEntries) {
          const attribute = opening.attributes.properties.find(
            (candidate) =>
              ts.isJsxAttribute(candidate) &&
              candidate.name.text === descriptor.prop,
          );
          if (!attribute) continue;
          const propSymbol = propsType
            ? checker.getPropertyOfType(propsType, descriptor.prop)
            : undefined;
          const propDeclaration = propSymbol?.declarations?.[0];
          if (!facts.has(key)) {
            facts.set(key, {
              descriptorId: descriptor.descriptorId,
              component: identity.component,
              componentDeclarationPath,
              componentDeclarationLine: lineOf(
                declaration.getSourceFile(),
                declaration,
              ),
              componentDeclarationSha256: textSha256(
                declaration.getText(declaration.getSourceFile()),
              ),
              prop: descriptor.prop,
              propDeclarationPath: propDeclaration
                ? declarationPath(propDeclaration)
                : null,
              propDeclarationLine: propDeclaration
                ? lineOf(propDeclaration.getSourceFile(), propDeclaration)
                : null,
              propDeclarationSha256: propDeclaration
                ? textSha256(
                    propDeclaration.getText(propDeclaration.getSourceFile()),
                  )
                : null,
              consumerSites: [],
            });
          }
          facts
            .get(key)
            .consumerSites.push(siteReceipt(sourceFile, attribute, pathOf));
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return [...facts.values()]
    .map((fact) => ({
      ...fact,
      consumerSites: fact.consumerSites.sort((left, right) =>
        `${left.path}:${String(left.line).padStart(8, "0")}`.localeCompare(
          `${right.path}:${String(right.line).padStart(8, "0")}`,
        ),
      ),
    }))
    .sort((left, right) => left.descriptorId.localeCompare(right.descriptorId));
}

function moduleExports(checker, sourceFile) {
  const moduleSymbol =
    checker.getSymbolAtLocation(sourceFile) ?? sourceFile.symbol;
  if (!moduleSymbol) return [];
  return checker.getExportsOfModule(moduleSymbol).map((symbol) => {
    if ((symbol.flags & ts.SymbolFlags.Alias) !== 0) {
      return checker.getAliasedSymbol(symbol);
    }
    return symbol;
  });
}

function privateUniqueBrandSymbol(checker, declaration) {
  if (!ts.isComputedPropertyName(declaration.name)) return undefined;
  const symbol = symbolIdentity(checker, declaration.name.expression);
  const brandDeclaration = symbol?.valueDeclaration;
  if (!brandDeclaration || !ts.isVariableDeclaration(brandDeclaration)) {
    return undefined;
  }
  const statement = brandDeclaration.parent?.parent;
  if (
    !ts.isVariableStatement(statement) ||
    statement.modifiers?.some(
      (modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword,
    )
  ) {
    return undefined;
  }
  const brandType = checker.getTypeAtLocation(brandDeclaration.name);
  return (brandType.flags & ts.TypeFlags.UniqueESSymbol) !== 0
    ? symbol
    : undefined;
}

function typeTouchesAuthorityBrand(
  checker,
  type,
  brandSymbols,
  seen = new Set(),
  depth = 0,
) {
  if (!type || seen.has(type) || depth > 10) return false;
  seen.add(type);
  for (const property of checker.getPropertiesOfType(type)) {
    for (const declaration of property.declarations ?? []) {
      const brand = privateUniqueBrandSymbol(checker, declaration);
      if (brand && brandSymbols.has(brand)) return true;
    }
    const declaration = property.valueDeclaration ?? property.declarations?.[0];
    if (
      declaration &&
      typeTouchesAuthorityBrand(
        checker,
        checker.getTypeOfSymbolAtLocation(property, declaration),
        brandSymbols,
        seen,
        depth + 1,
      )
    ) {
      return true;
    }
  }
  for (const member of type.types ?? []) {
    if (
      typeTouchesAuthorityBrand(checker, member, brandSymbols, seen, depth + 1)
    ) {
      return true;
    }
  }
  for (const argument of type.aliasTypeArguments ?? type.typeArguments ?? []) {
    if (
      typeTouchesAuthorityBrand(
        checker,
        argument,
        brandSymbols,
        seen,
        depth + 1,
      )
    ) {
      return true;
    }
  }
  for (const signature of [
    ...checker.getSignaturesOfType(type, ts.SignatureKind.Call),
    ...checker.getSignaturesOfType(type, ts.SignatureKind.Construct),
  ]) {
    if (
      typeTouchesAuthorityBrand(
        checker,
        checker.getReturnTypeOfSignature(signature),
        brandSymbols,
        seen,
        depth + 1,
      )
    ) {
      return true;
    }
    for (const parameter of signature.getParameters()) {
      const declaration =
        parameter.valueDeclaration ?? parameter.declarations?.[0];
      if (
        declaration &&
        typeTouchesAuthorityBrand(
          checker,
          checker.getTypeOfSymbolAtLocation(parameter, declaration),
          brandSymbols,
          seen,
          depth + 1,
        )
      ) {
        return true;
      }
    }
  }
  return false;
}

function collectBrandsInType(
  checker,
  type,
  brands,
  seen = new Set(),
  depth = 0,
) {
  if (!type || seen.has(type) || depth > 10) return;
  seen.add(type);
  for (const property of checker.getPropertiesOfType(type)) {
    for (const declaration of property.declarations ?? []) {
      const brand = privateUniqueBrandSymbol(checker, declaration);
      if (brand) brands.add(brand);
    }
    const declaration = property.valueDeclaration ?? property.declarations?.[0];
    if (declaration) {
      collectBrandsInType(
        checker,
        checker.getTypeOfSymbolAtLocation(property, declaration),
        brands,
        seen,
        depth + 1,
      );
    }
  }
  for (const member of type.types ?? []) {
    collectBrandsInType(checker, member, brands, seen, depth + 1);
  }
  for (const argument of type.aliasTypeArguments ?? type.typeArguments ?? []) {
    collectBrandsInType(checker, argument, brands, seen, depth + 1);
  }
}

function emptyAuthorityIssuerFacts() {
  return {
    modules: [],
    brands: [],
    factories: [],
    stores: [],
    privateConstructors: [],
    exhaustiveToneMaps: [],
    exactGeneratedScalars: [],
    parityBindings: [],
    unrecognizedNeutralFactories: [],
    ownerMembershipFactories: [],
    exportedValueConstants: [],
  };
}

function enclosingFunctionName(checker, node) {
  const enclosing = enclosingFunctionNode(node);
  return enclosing ? (functionSymbol(checker, enclosing)?.name ?? null) : null;
}

function enclosingFunctionNode(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isFunctionLike(current)) return current;
  }
  return null;
}

function returnBrandNames(checker, signature, brands) {
  const returnType = checker.getReturnTypeOfSignature(signature);
  return brands
    .filter(({ symbol }) =>
      typeTouchesAuthorityBrand(checker, returnType, new Set([symbol])),
    )
    .map(({ name }) => name)
    .sort();
}

function typeNodeReferencesGeneratedDefinition(
  checker,
  typeNode,
  governedPaths,
  seenSymbols = new Set(),
) {
  let found = false;
  const visit = (node) => {
    if (found) return;
    const symbol =
      ts.isIdentifier(node) || ts.isQualifiedName(node)
        ? symbolIdentity(checker, node)
        : undefined;
    if (symbol && !seenSymbols.has(symbol)) {
      seenSymbols.add(symbol);
      const declarations = symbol.declarations ?? [];
      if (
        declarations.some((declaration) =>
          governedPaths.has(declarationPath(declaration)),
        )
      ) {
        found = true;
        return;
      }
      for (const declaration of declarations) {
        if (ts.isTypeAliasDeclaration(declaration)) {
          visit(declaration.type);
        }
      }
    }
    if (!found) ts.forEachChild(node, visit);
  };
  visit(typeNode);
  return found;
}

function objectLiteralInitializesBrand(checker, objectLiteral, brandSymbol) {
  return objectLiteral.properties.some(
    (property) =>
      ts.isPropertyAssignment(property) &&
      ts.isComputedPropertyName(property.name) &&
      symbolIdentity(checker, property.name.expression) === brandSymbol,
  );
}

function callAuthorityBrandNames(checker, call, brands) {
  const signature = checker.getResolvedSignature(call);
  return signature ? returnBrandNames(checker, signature, brands) : [];
}

function directRootIdentifier(node) {
  let current = unwrapExpression(node);
  while (
    ts.isPropertyAccessExpression(current) ||
    ts.isElementAccessExpression(current)
  ) {
    current = unwrapExpression(current.expression);
  }
  return ts.isIdentifier(current) ? current : null;
}

function isCanonicalTypeScriptLibSymbol(checker, node, expectedName) {
  const symbol = symbolIdentity(checker, node);
  const declarations = symbol?.declarations ?? [];
  return (
    symbol?.name === expectedName &&
    declarations.length > 0 &&
    declarations.every((declaration) => {
      const sourceFile = declaration.getSourceFile();
      return (
        sourceFile.hasNoDefaultLib &&
        /\/typescript\/lib\/lib\.[^/]+\.d\.ts$/u.test(
          sourceFile.fileName.split(path.sep).join("/"),
        )
      );
    })
  );
}

function isCanonicalObjectFreezeCall(checker, node) {
  return (
    ts.isCallExpression(node) &&
    ts.isPropertyAccessExpression(node.expression) &&
    isCanonicalTypeScriptLibSymbol(
      checker,
      node.expression.expression,
      "Object",
    ) &&
    isCanonicalTypeScriptLibSymbol(checker, node.expression.name, "freeze")
  );
}

function closedStringValues(type) {
  const members = type?.isUnion?.() ? type.types : type ? [type] : [];
  return members.length > 0 &&
    members.every((member) => (member.flags & ts.TypeFlags.StringLiteral) !== 0)
    ? members.map((member) => member.value).sort()
    : [];
}

function literalExpressionStrings(node, values = new Set()) {
  const current = unwrapExpression(node);
  if (ts.isStringLiteralLike(current)) {
    values.add(current.text);
  } else if (ts.isArrayLiteralExpression(current)) {
    for (const element of current.elements) {
      literalExpressionStrings(element, values);
    }
  } else if (ts.isObjectLiteralExpression(current)) {
    for (const property of current.properties) {
      if (ts.isPropertyAssignment(property)) {
        const name = propertyNameText(property.name);
        if (name) values.add(name);
        literalExpressionStrings(property.initializer, values);
      }
    }
  } else {
    ts.forEachChild(current, (child) =>
      literalExpressionStrings(child, values),
    );
  }
  return values;
}

function stringPropertyValue(node, name) {
  const property = node.properties.find(
    (candidate) =>
      ts.isPropertyAssignment(candidate) &&
      propertyNameText(candidate.name) === name,
  );
  if (!property || !ts.isPropertyAssignment(property)) return null;
  const value = unwrapExpression(property.initializer);
  return ts.isStringLiteralLike(value) ? value.text : null;
}

function directReturnStatementForCall(call) {
  let expression = call;
  while (
    expression.parent &&
    (ts.isParenthesizedExpression(expression.parent) ||
      ts.isAsExpression(expression.parent) ||
      ts.isTypeAssertionExpression(expression.parent) ||
      ts.isNonNullExpression(expression.parent) ||
      ts.isSatisfiesExpression(expression.parent) ||
      ts.isPartiallyEmittedExpression(expression.parent)) &&
    expression.parent.expression === expression
  ) {
    expression = expression.parent;
  }
  return ts.isReturnStatement(expression.parent) &&
    expression.parent.expression === expression
    ? expression.parent
    : null;
}

function directReturnPlacement(returnStatement, functionBody) {
  if (returnStatement.parent === functionBody) return "top_level";
  const block = returnStatement.parent;
  const conditional = block?.parent;
  return ts.isBlock(block) &&
    ts.isIfStatement(conditional) &&
    conditional.parent === functionBody &&
    conditional.thenStatement === block
    ? "top_level_if"
    : "other";
}

function brandedCallPosture(call) {
  const objectArgument = call.arguments
    .map((argument) => unwrapExpression(argument))
    .find((argument) => ts.isObjectLiteralExpression(argument));
  return {
    presentation: objectArgument
      ? stringPropertyValue(objectArgument, "presentation")
      : null,
    source: objectArgument
      ? stringPropertyValue(objectArgument, "source")
      : null,
    tone: objectArgument ? stringPropertyValue(objectArgument, "tone") : null,
  };
}

function negatedIncludesCall(node) {
  const condition = unwrapExpression(node.expression);
  if (
    !ts.isPrefixUnaryExpression(condition) ||
    condition.operator !== ts.SyntaxKind.ExclamationToken
  ) {
    return null;
  }
  const call = unwrapExpression(condition.operand);
  return ts.isCallExpression(call) &&
    ts.isPropertyAccessExpression(call.expression) &&
    call.expression.name.text === "includes"
    ? call
    : null;
}

function statementThrows(statement) {
  return (
    ts.isThrowStatement(statement) ||
    (ts.isBlock(statement) &&
      statement.statements.some((child) => ts.isThrowStatement(child)))
  );
}

function literalTypeHasKind(node, syntaxKind) {
  return ts.isLiteralTypeNode(node) && node.literal.kind === syntaxKind;
}

function numericLiteralTypeIs(node, value) {
  return (
    ts.isLiteralTypeNode(node) &&
    ts.isNumericLiteral(node.literal) &&
    node.literal.text === String(value)
  );
}

function typeReferenceSymbol(checker, node) {
  return ts.isTypeReferenceNode(node)
    ? symbolIdentity(checker, node.typeName)
    : null;
}

function isAssignabilityProbe(checker, node, targetSymbol) {
  let current = node;
  while (ts.isParenthesizedTypeNode(current)) current = current.type;
  if (
    !ts.isFunctionTypeNode(current) ||
    current.parameters.length !== 0 ||
    current.typeParameters?.length !== 1 ||
    !ts.isConditionalTypeNode(current.type)
  ) {
    return false;
  }
  const valueSymbol = symbolIdentity(checker, current.typeParameters[0].name);
  return (
    Boolean(valueSymbol) &&
    typeReferenceSymbol(checker, current.type.checkType) === valueSymbol &&
    typeReferenceSymbol(checker, current.type.extendsType) === targetSymbol &&
    numericLiteralTypeIs(current.type.trueType, 1) &&
    numericLiteralTypeIs(current.type.falseType, 2)
  );
}

function isExactTwoWayPredicate(checker, declaration) {
  if (
    !ts.isTypeAliasDeclaration(declaration) ||
    declaration.typeParameters?.length !== 2 ||
    !ts.isConditionalTypeNode(declaration.type)
  ) {
    return false;
  }
  const left = symbolIdentity(checker, declaration.typeParameters[0].name);
  const right = symbolIdentity(checker, declaration.typeParameters[1].name);
  const outer = declaration.type;
  const reverse = outer.trueType;
  return (
    Boolean(left && right) &&
    isAssignabilityProbe(checker, outer.checkType, left) &&
    isAssignabilityProbe(checker, outer.extendsType, right) &&
    ts.isConditionalTypeNode(reverse) &&
    isAssignabilityProbe(checker, reverse.checkType, right) &&
    isAssignabilityProbe(checker, reverse.extendsType, left) &&
    literalTypeHasKind(reverse.trueType, ts.SyntaxKind.TrueKeyword) &&
    literalTypeHasKind(reverse.falseType, ts.SyntaxKind.FalseKeyword) &&
    literalTypeHasKind(outer.falseType, ts.SyntaxKind.FalseKeyword)
  );
}

function parityParameterPredicate(checker, typeNode) {
  if (
    !ts.isConditionalTypeNode(typeNode) ||
    !ts.isTypeReferenceNode(typeNode.checkType) ||
    typeNode.checkType.typeArguments?.length !== 2
  ) {
    return null;
  }
  return {
    symbol: typeReferenceSymbol(checker, typeNode.checkType),
    neverFailure:
      literalTypeHasKind(typeNode.extendsType, ts.SyntaxKind.TrueKeyword) &&
      literalTypeHasKind(typeNode.trueType, ts.SyntaxKind.TrueKeyword) &&
      typeNode.falseType.kind === ts.SyntaxKind.NeverKeyword,
  };
}

function collectAuthorityIssuerFacts(
  checker,
  sourceByPath,
  brandSymbols,
  generatedDefinitionPaths,
) {
  const facts = emptyAuthorityIssuerFacts();
  const governedPaths = new Set(generatedDefinitionPaths ?? []);
  const brands = [...brandSymbols]
    .map((symbol) => {
      const declaration =
        symbol.valueDeclaration ?? symbol.declarations?.[0] ?? null;
      const sourceFile = declaration?.getSourceFile();
      const issuerPath = declaration ? declarationPath(declaration) : null;
      return declaration && sourceFile && issuerPath
        ? {
            symbol,
            name: symbol.name,
            path: issuerPath,
            line: lineOf(sourceFile, declaration),
            declarationSha256: textSha256(declaration.getText(sourceFile)),
          }
        : null;
    })
    .filter(Boolean)
    .sort((left, right) =>
      `${left.path}:${left.name}`.localeCompare(`${right.path}:${right.name}`),
    );
  const modulePaths = [
    ...new Set(brands.map(({ path: issuerPath }) => issuerPath)),
  ].sort();
  const moduleSources = modulePaths
    .map((issuerPath) => sourceByPath.get(issuerPath))
    .filter(Boolean);
  facts.modules = moduleSources.map((sourceFile) => ({
    path: relativePath(sourceFile.fileName),
    sourceSha256: textSha256(sourceFile.text),
  }));

  const exportedSymbols = new Set(
    moduleSources.flatMap((sourceFile) => moduleExports(checker, sourceFile)),
  );
  facts.brands = brands.map(({ symbol, ...fact }) => ({
    ...fact,
    exported: exportedSymbols.has(symbol),
  }));
  const generatedSemanticSets = [];
  for (const sourceFile of moduleSources) {
    const visitGeneratedVocabularies = (node) => {
      if (
        ts.isSatisfiesExpression(node) &&
        isGeneratedToneMapTarget(checker, node.type, governedPaths)
      ) {
        const keyType = node.type.typeArguments[0];
        const values = closedStringValues(checker.getTypeFromTypeNode(keyType));
        if (values.length > 0) generatedSemanticSets.push(new Set(values));
      }
      ts.forEachChild(node, visitGeneratedVocabularies);
    };
    visitGeneratedVocabularies(sourceFile);
  }
  const storeSymbols = new Map();
  for (const sourceFile of moduleSources) {
    const visitStores = (node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer &&
        ts.isNewExpression(node.initializer) &&
        ts.isIdentifier(node.initializer.expression) &&
        ["WeakMap", "WeakSet"].includes(node.initializer.expression.text) &&
        isCanonicalTypeScriptLibSymbol(
          checker,
          node.initializer.expression,
          node.initializer.expression.text,
        )
      ) {
        const symbol = symbolIdentity(checker, node.name);
        if (symbol) {
          const row = {
            symbol,
            name: node.name.text,
            kind: node.initializer.expression.text,
            path: relativePath(sourceFile.fileName),
            line: lineOf(sourceFile, node),
            exported: exportedSymbols.has(symbol),
            reads: [],
            writes: [],
          };
          storeSymbols.set(symbol, row);
        }
      }
      ts.forEachChild(node, visitStores);
    };
    visitStores(sourceFile);
  }

  const factoryDeclarations = new Map();
  for (const sourceFile of moduleSources) {
    for (const symbol of moduleExports(checker, sourceFile)) {
      const declaration = symbol.valueDeclaration ?? symbol.declarations?.[0];
      if (!declaration) continue;
      const valueType = checker.getTypeOfSymbolAtLocation(symbol, declaration);
      const initializer = declaration.initializer ?? null;
      const literalValues = initializer
        ? literalExpressionStrings(initializer)
        : new Set();
      const valuePropertyNames = new Set(
        checker.getPropertiesOfType(valueType).map((property) => property.name),
      );
      const reconstructsGeneratedVocabulary = generatedSemanticSets.some(
        (semanticIds) =>
          semanticIds.size > 0 &&
          [...semanticIds].some(
            (semanticId) =>
              literalValues.has(semanticId) ||
              valuePropertyNames.has(semanticId),
          ),
      );
      const isGeneratedVocabulary = Boolean(
        ts.isVariableDeclaration(declaration) &&
        ((declaration.type &&
          typeNodeReferencesGeneratedDefinition(
            checker,
            declaration.type,
            governedPaths,
          )) ||
          (initializer &&
            ts.isSatisfiesExpression(initializer) &&
            isGeneratedToneMapTarget(
              checker,
              initializer.type,
              governedPaths,
            )) ||
          reconstructsGeneratedVocabulary),
      );
      if (ts.isVariableDeclaration(declaration) && isGeneratedVocabulary) {
        facts.exportedValueConstants.push({
          name: symbol.name,
          path: relativePath(sourceFile.fileName),
          line: lineOf(sourceFile, declaration),
        });
      }
      const signatures = checker.getSignaturesOfType(
        valueType,
        ts.SignatureKind.Call,
      );
      const signature = signatures.find(
        (candidate) => returnBrandNames(checker, candidate, brands).length > 0,
      );
      if (!signature) continue;
      const parameters = signature.getParameters().map((parameter) => {
        const parameterDeclaration =
          parameter.valueDeclaration ?? parameter.declarations?.[0];
        const proof = parameterDeclaration?.type
          ? terminalTypeDeclarationPaths(checker, parameterDeclaration.type)
          : { paths: new Set(), complete: false };
        const parameterType = parameterDeclaration
          ? checker.getTypeOfSymbolAtLocation(parameter, parameterDeclaration)
          : null;
        return {
          name: parameter.name,
          type: parameterDeclaration?.type?.getText(sourceFile) ?? null,
          generated:
            proof.complete &&
            proof.paths.size > 0 &&
            [...proof.paths].every((candidatePath) =>
              governedPaths.has(candidatePath),
            ),
          generatedPaths: [...proof.paths].sort(),
          broadString: Boolean(
            parameterType && (parameterType.flags & ts.TypeFlags.String) !== 0,
          ),
        };
      });
      const row = {
        name: symbol.name,
        path: relativePath(sourceFile.fileName),
        line: lineOf(sourceFile, declaration),
        declarationSha256: textSha256(declaration.getText(sourceFile)),
        overloadCount: signatures.length,
        returnBrands: returnBrandNames(checker, signature, brands),
        parameters: parameters.map((parameter, index) => {
          const parameterDeclaration =
            signature.getParameters()[index]?.valueDeclaration;
          return {
            ...parameter,
            optional: Boolean(
              parameterDeclaration?.questionToken ||
              parameterDeclaration?.initializer,
            ),
            rest: Boolean(parameterDeclaration?.dotDotDotToken),
          };
        }),
      };
      facts.factories.push(row);
      factoryDeclarations.set(symbol.name, { declaration, row });
    }
  }

  for (const sourceFile of moduleSources) {
    const visit = (node) => {
      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression)
      ) {
        const store = storeSymbols.get(
          symbolIdentity(checker, unwrapExpression(node.expression.expression)),
        );
        if (store) {
          const method = node.expression.name.text;
          const enclosing = enclosingFunctionNode(node);
          const argumentSymbol = node.arguments[0]
            ? symbolIdentity(checker, unwrapExpression(node.arguments[0]))
            : null;
          const argumentParameter = enclosing?.parameters
            .filter((parameter) => ts.isIdentifier(parameter.name))
            .find(
              (parameter) =>
                symbolIdentity(checker, parameter.name) === argumentSymbol,
            )?.name.text;
          const operation = {
            function: enclosingFunctionName(checker, node),
            method,
          };
          if (["add", "set"].includes(method)) store.writes.push(operation);
          if (["get", "has"].includes(method)) {
            store.reads.push({
              ...operation,
              argumentParameter: argumentParameter ?? null,
            });
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  facts.stores = [...storeSymbols.values()]
    .map(({ symbol: _symbol, ...row }) => ({
      ...row,
      reads: row.reads.sort((left, right) =>
        `${left.function}:${left.method}`.localeCompare(
          `${right.function}:${right.method}`,
        ),
      ),
      writes: row.writes.sort((left, right) =>
        `${left.function}:${left.method}`.localeCompare(
          `${right.function}:${right.method}`,
        ),
      ),
    }))
    .sort((left, right) => left.name.localeCompare(right.name));

  for (const sourceFile of moduleSources) {
    const visit = (node) => {
      if (ts.isFunctionDeclaration(node) && node.name && node.body) {
        const symbol = symbolIdentity(checker, node.name);
        const signature = checker
          .getSignaturesOfType(
            checker.getTypeAtLocation(node.name),
            ts.SignatureKind.Call,
          )
          .find(
            (candidate) =>
              returnBrandNames(checker, candidate, brands).length > 0,
          );
        if (signature && symbol && !exportedSymbols.has(symbol)) {
          let freezeCalls = 0;
          let returnedFrozenSymbol = null;
          let brandedBindingSymbol = null;
          const constructorWrites = [];
          const inspectBody = (child) => {
            if (child !== node && ts.isFunctionLike(child)) return;
            if (
              ts.isVariableDeclaration(child) &&
              ts.isIdentifier(child.name) &&
              child.initializer &&
              ts.isObjectLiteralExpression(
                unwrapExpression(child.initializer),
              ) &&
              returnBrandNames(checker, signature, brands).some((brandName) => {
                const brand = brands.find(({ name }) => name === brandName);
                return Boolean(
                  brand &&
                  objectLiteralInitializesBrand(
                    checker,
                    unwrapExpression(child.initializer),
                    brand.symbol,
                  ),
                );
              })
            ) {
              brandedBindingSymbol = symbolIdentity(checker, child.name);
            }
            if (isCanonicalObjectFreezeCall(checker, child)) {
              freezeCalls += 1;
            }
            if (
              ts.isReturnStatement(child) &&
              child.expression &&
              ts.isCallExpression(unwrapExpression(child.expression))
            ) {
              const call = unwrapExpression(child.expression);
              if (
                isCanonicalObjectFreezeCall(checker, call) &&
                call.arguments.length === 1
              ) {
                returnedFrozenSymbol = symbolIdentity(
                  checker,
                  unwrapExpression(call.arguments[0]),
                );
              }
            }
            if (
              ts.isCallExpression(child) &&
              ts.isPropertyAccessExpression(child.expression)
            ) {
              const store = storeSymbols.get(
                symbolIdentity(
                  checker,
                  unwrapExpression(child.expression.expression),
                ),
              );
              if (
                store &&
                ["add", "set"].includes(child.expression.name.text)
              ) {
                constructorWrites.push({
                  store: store.name,
                  method: child.expression.name.text,
                  argumentSymbol: child.arguments[0]
                    ? symbolIdentity(
                        checker,
                        unwrapExpression(child.arguments[0]),
                      )
                    : null,
                });
              }
            }
            ts.forEachChild(child, inspectBody);
          };
          inspectBody(node.body);
          facts.privateConstructors.push({
            name: node.name.text,
            path: relativePath(sourceFile.fileName),
            line: lineOf(sourceFile, node),
            returnBrands: returnBrandNames(checker, signature, brands),
            freezeCalls,
            returnedValueFrozen: Boolean(returnedFrozenSymbol),
            brandInitializedOnReturnedValue:
              Boolean(returnedFrozenSymbol) &&
              returnedFrozenSymbol === brandedBindingSymbol,
            issuanceWrites: constructorWrites
              .map(({ store, method, argumentSymbol }) => ({
                store,
                method,
                issuedValue:
                  Boolean(returnedFrozenSymbol) &&
                  argumentSymbol === returnedFrozenSymbol,
              }))
              .sort((left, right) =>
                `${left.store}:${left.method}`.localeCompare(
                  `${right.store}:${right.method}`,
                ),
              ),
          });
        }

        if (
          node.parameters.length === 1 &&
          node.parameters[0].type &&
          node.type &&
          ts.isIdentifier(node.parameters[0].name) &&
          isGeneratedClosedInputType(
            checker,
            node.parameters[0].type,
            governedPaths,
          ) &&
          isClosedStringLiteralType(checker.getTypeFromTypeNode(node.type)) &&
          node.body.statements.length === 1 &&
          ts.isReturnStatement(node.body.statements[0]) &&
          ts.isIdentifier(node.body.statements[0].expression) &&
          node.body.statements[0].expression.text ===
            node.parameters[0].name.text
        ) {
          const scalarCallers = new Set();
          const visitScalarCalls = (child) => {
            if (
              ts.isCallExpression(child) &&
              symbolIdentity(checker, child.expression) === symbol
            ) {
              const caller = enclosingFunctionName(checker, child);
              if (caller) scalarCallers.add(caller);
            }
            ts.forEachChild(child, visitScalarCalls);
          };
          visitScalarCalls(sourceFile);
          facts.exactGeneratedScalars.push({
            name: node.name.text,
            path: relativePath(sourceFile.fileName),
            line: lineOf(sourceFile, node),
            input: node.parameters[0].type.getText(sourceFile),
            output: node.type.getText(sourceFile),
            callers: [...scalarCallers].sort(),
          });
        }

        const resolvedParameters = node.parameters.map((parameter) =>
          parameter.type ? checker.getTypeFromTypeNode(parameter.type) : null,
        );
        if (
          resolvedParameters.length > 1 &&
          node.parameters.every(
            (parameter) =>
              parameter.type &&
              typeNodeReferencesGeneratedDefinition(
                checker,
                parameter.type,
                governedPaths,
              ),
          ) &&
          resolvedParameters.every(
            (type) =>
              type &&
              (type.flags & ts.TypeFlags.BooleanLiteral) !== 0 &&
              type.intrinsicName === "true",
          )
        ) {
          const predicateParameters = node.parameters.map((parameter) =>
            parameter.type
              ? parityParameterPredicate(checker, parameter.type)
              : null,
          );
          const predicateSymbol =
            predicateParameters.length > 0 &&
            predicateParameters[0]?.symbol &&
            predicateParameters.every(
              (parameter) =>
                parameter?.symbol === predicateParameters[0].symbol,
            )
              ? predicateParameters[0].symbol
              : null;
          const predicateDeclaration = predicateSymbol?.declarations?.find(
            (declaration) => ts.isTypeAliasDeclaration(declaration),
          );
          let totalInvocations = 0;
          let literalTrueInvocations = 0;
          const visitParityCalls = (child) => {
            if (
              ts.isCallExpression(child) &&
              symbolIdentity(checker, child.expression) === symbol &&
              ts.isExpressionStatement(child.parent) &&
              child.parent.parent === sourceFile
            ) {
              totalInvocations += 1;
              if (
                child.arguments.length === resolvedParameters.length &&
                child.arguments.every(
                  (argument) =>
                    unwrapExpression(argument).kind ===
                    ts.SyntaxKind.TrueKeyword,
                )
              ) {
                literalTrueInvocations += 1;
              }
            }
            ts.forEachChild(child, visitParityCalls);
          };
          visitParityCalls(sourceFile);
          facts.parityBindings.push({
            name: node.name.text,
            path: relativePath(sourceFile.fileName),
            line: lineOf(sourceFile, node),
            parameters: resolvedParameters.length,
            totalInvocations,
            literalTrueInvocations,
            neverFailureParameters: predicateParameters.filter(
              (parameter) => parameter?.neverFailure,
            ).length,
            predicate:
              predicateDeclaration && predicateSymbol
                ? {
                    name: predicateSymbol.name,
                    path: declarationPath(predicateDeclaration),
                    exactTwoWay: isExactTwoWayPredicate(
                      checker,
                      predicateDeclaration,
                    ),
                  }
                : null,
          });
        }
      }

      if (
        ts.isSatisfiesExpression(node) &&
        isExhaustiveGeneratedToneMap(checker, node.type, governedPaths)
      ) {
        const declaration = ts.isVariableDeclaration(node.parent)
          ? node.parent
          : null;
        const mapSymbol =
          declaration && ts.isIdentifier(declaration.name)
            ? symbolIdentity(checker, declaration.name)
            : null;
        const consumers = new Set();
        if (mapSymbol) {
          const visitMapUses = (child) => {
            if (
              ts.isElementAccessExpression(child) &&
              symbolIdentity(checker, unwrapExpression(child.expression)) ===
                mapSymbol
            ) {
              const consumer = enclosingFunctionName(checker, child);
              if (consumer) consumers.add(consumer);
            }
            ts.forEachChild(child, visitMapUses);
          };
          visitMapUses(sourceFile);
        }
        facts.exhaustiveToneMaps.push({
          path: relativePath(sourceFile.fileName),
          line: lineOf(sourceFile, node),
          target: node.type.getText(sourceFile),
          consumers: [...consumers].sort(),
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  for (const [factoryName, { declaration, row }] of factoryDeclarations) {
    const issuedReturns = [];
    const issuanceCalls = [];
    const ownerMembership = [];
    let returnStatements = 0;
    const sourceFile = declaration.getSourceFile();
    const parameterSymbols = new Map();
    for (const parameter of declaration.parameters ?? []) {
      if (!ts.isIdentifier(parameter.name) || !parameter.type) continue;
      const proof = terminalTypeDeclarationPaths(checker, parameter.type);
      if (
        proof.complete &&
        proof.paths.size > 0 &&
        [...proof.paths].every((candidatePath) =>
          governedPaths.has(candidatePath),
        )
      ) {
        parameterSymbols.set(
          symbolIdentity(checker, parameter.name),
          parameter.name.text,
        );
      }
    }
    const visit = (node) => {
      if (node !== declaration && ts.isFunctionLike(node)) return;
      if (ts.isReturnStatement(node)) returnStatements += 1;
      if (ts.isCallExpression(node)) {
        const returnedBrands = callAuthorityBrandNames(checker, node, brands);
        if (returnedBrands.some((brand) => row.returnBrands.includes(brand))) {
          const returnStatement = directReturnStatementForCall(node);
          const callFact = {
            position: node.getStart(sourceFile),
            ...brandedCallPosture(node),
            directReturn: Boolean(returnStatement),
            placement: returnStatement
              ? directReturnPlacement(returnStatement, declaration.body)
              : null,
          };
          issuanceCalls.push(callFact);
          if (returnStatement) issuedReturns.push(callFact);
        }
      }

      if (
        ts.isIfStatement(node) &&
        node.parent === declaration.body &&
        statementThrows(node.thenStatement)
      ) {
        const membershipCall = negatedIncludesCall(node);
        const receiver = membershipCall
          ? directRootIdentifier(membershipCall.expression.expression)
          : null;
        const argument = membershipCall?.arguments[0]
          ? unwrapExpression(membershipCall.arguments[0])
          : null;
        const receiverParameter = receiver
          ? parameterSymbols.get(symbolIdentity(checker, receiver))
          : undefined;
        const argumentParameter =
          argument && ts.isIdentifier(argument)
            ? parameterSymbols.get(symbolIdentity(checker, argument))
            : undefined;
        if (membershipCall && argumentParameter) {
          const receiverExpression = unwrapExpression(
            membershipCall.expression.expression,
          );
          ownerMembership.push({
            factory: factoryName,
            position: node.getStart(sourceFile),
            receiverParameter: receiverParameter ?? null,
            receiverProperty:
              receiverParameter &&
              ts.isPropertyAccessExpression(receiverExpression)
                ? receiverExpression.name.text
                : null,
            argumentParameter,
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(declaration);
    issuedReturns.sort((left, right) => left.position - right.position);
    issuanceCalls.sort((left, right) => left.position - right.position);
    row.issuedReturns = issuedReturns.map(
      ({
        position: _position,
        directReturn: _direct,
        placement: _placement,
        ...returnFact
      }) => returnFact,
    );
    row.issuanceCalls = issuanceCalls.map(
      ({ position: _position, ...callFact }) => callFact,
    );
    row.returnStatements = returnStatements;
    if (
      issuedReturns.some(
        (returnFact) =>
          returnFact.presentation === "unrecognized" &&
          returnFact.tone === "neutral",
      )
    ) {
      facts.unrecognizedNeutralFactories.push(factoryName);
    }
    const firstIssuance =
      issuanceCalls[0]?.position ?? Number.POSITIVE_INFINITY;
    facts.ownerMembershipFactories.push(
      ...ownerMembership.map(({ position, ...membership }) => ({
        ...membership,
        negatedThrow: true,
        precedesIssuance: position < firstIssuance,
      })),
    );
  }

  facts.factories.sort((left, right) => left.name.localeCompare(right.name));
  facts.privateConstructors.sort((left, right) =>
    left.name.localeCompare(right.name),
  );
  facts.exhaustiveToneMaps.sort((left, right) =>
    `${left.path}:${left.line}`.localeCompare(`${right.path}:${right.line}`),
  );
  facts.exactGeneratedScalars.sort((left, right) =>
    left.name.localeCompare(right.name),
  );
  facts.parityBindings.sort((left, right) =>
    left.name.localeCompare(right.name),
  );
  facts.unrecognizedNeutralFactories.sort();
  facts.ownerMembershipFactories.sort((left, right) =>
    `${left.factory}:${left.receiverParameter}:${left.receiverProperty}:${left.argumentParameter}`.localeCompare(
      `${right.factory}:${right.receiverParameter}:${right.receiverProperty}:${right.argumentParameter}`,
    ),
  );
  facts.exportedValueConstants.sort((left, right) =>
    `${left.path}:${left.name}`.localeCompare(`${right.path}:${right.name}`),
  );
  return facts;
}

function componentPropType(checker, sourceFile, descriptor) {
  const component = moduleExports(checker, sourceFile).find(
    (symbol) => symbol.name === descriptor.component,
  );
  const declaration =
    component?.valueDeclaration ?? component?.declarations?.[0];
  if (!component || !declaration) return null;
  const componentType = checker.getTypeOfSymbolAtLocation(
    component,
    declaration,
  );
  for (const signature of checker.getSignaturesOfType(
    componentType,
    ts.SignatureKind.Call,
  )) {
    const parameter = signature.getParameters()[0];
    const parameterDeclaration =
      parameter?.valueDeclaration ?? parameter?.declarations?.[0];
    if (!parameter || !parameterDeclaration) continue;
    const props = checker.getTypeOfSymbolAtLocation(
      parameter,
      parameterDeclaration,
    );
    const property = checker.getPropertyOfType(props, descriptor.prop);
    const propertyDeclaration =
      property?.valueDeclaration ?? property?.declarations?.[0];
    if (property && propertyDeclaration) {
      return checker.getTypeOfSymbolAtLocation(property, propertyDeclaration);
    }
  }
  return null;
}

function sourceImportsAuthorityFamily(checker, sourceFile, familySymbols) {
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause) continue;
    const clause = statement.importClause;
    if (
      clause.name &&
      familySymbols.has(symbolIdentity(checker, clause.name))
    ) {
      return true;
    }
    const bindings = clause.namedBindings;
    if (bindings && ts.isNamedImports(bindings)) {
      if (
        bindings.elements.some((element) =>
          familySymbols.has(symbolIdentity(checker, element.name)),
        )
      ) {
        return true;
      }
    } else if (bindings && ts.isNamespaceImport(bindings)) {
      const namespaceBinding = checker.getSymbolAtLocation(bindings.name);
      const namespaceType = checker.getTypeAtLocation(bindings.name);
      let used = false;
      const visit = (node) => {
        if (
          ts.isPropertyAccessExpression(node) ||
          ts.isElementAccessExpression(node)
        ) {
          const expression = unwrapExpression(node.expression);
          if (checker.getSymbolAtLocation(expression) === namespaceBinding) {
            const memberName = ts.isPropertyAccessExpression(node)
              ? node.name.text
              : ts.isStringLiteralLike(node.argumentExpression)
                ? node.argumentExpression.text
                : null;
            let member = memberName
              ? checker.getPropertyOfType(namespaceType, memberName)
              : undefined;
            if (member && (member.flags & ts.SymbolFlags.Alias) !== 0) {
              member = checker.getAliasedSymbol(member);
            }
            if (member && familySymbols.has(member)) {
              used = true;
              return;
            }
          }
        }
        if (!used) ts.forEachChild(node, visit);
      };
      visit(sourceFile);
      if (used) return true;
    }
  }
  return false;
}

function hasAuthorityGovernanceEdge(sourceFile, componentNames, objectNames) {
  let found = false;
  const visit = (node) => {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      objectNames.has(node.name.text) &&
      node.initializer
    ) {
      const collection = unwrapExpression(node.initializer);
      if (ts.isObjectLiteralExpression(collection)) {
        const names = new Set(
          collection.properties
            .map((property) => propertyNameText(property.name))
            .filter(Boolean),
        );
        if ([...componentNames].every((name) => names.has(name))) found = true;
      } else if (ts.isArrayLiteralExpression(collection)) {
        const names = new Set(
          collection.elements
            .filter((element) => ts.isStringLiteralLike(element))
            .map((element) => element.text),
        );
        if ([...componentNames].every((name) => names.has(name))) found = true;
      }
    }
    if (!found) ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return found;
}

const anyUnknownTypeCache = new WeakMap();

function typeContainsAnyOrUnknown(checker, type, seen = new Set()) {
  if (!type) return false;
  let cache = anyUnknownTypeCache.get(checker);
  if (!cache) {
    cache = new Map();
    anyUnknownTypeCache.set(checker, cache);
  }
  if (cache.has(type)) return cache.get(type);
  if ((type.flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown)) !== 0) {
    cache.set(type, true);
    return true;
  }
  if (seen.has(type)) return false;
  seen.add(type);

  for (const member of type.types ?? []) {
    if (typeContainsAnyOrUnknown(checker, member, seen)) {
      cache.set(type, true);
      return true;
    }
  }
  const typeArguments = [
    ...(type.aliasTypeArguments ?? []),
    ...((type.flags & ts.TypeFlags.Object) !== 0 &&
    (type.objectFlags & ts.ObjectFlags.Reference) !== 0
      ? checker.getTypeArguments(type)
      : []),
  ];
  for (const argument of typeArguments) {
    if (typeContainsAnyOrUnknown(checker, argument, seen)) {
      cache.set(type, true);
      return true;
    }
  }
  if ((type.flags & ts.TypeFlags.TypeParameter) !== 0) {
    const constraint = checker.getBaseConstraintOfType(type);
    if (
      constraint &&
      constraint !== type &&
      typeContainsAnyOrUnknown(checker, constraint, seen)
    ) {
      cache.set(type, true);
      return true;
    }
  }
  if ((type.flags & ts.TypeFlags.Object) === 0) {
    cache.set(type, false);
    return false;
  }

  for (const indexType of [
    type.getStringIndexType(),
    type.getNumberIndexType(),
  ]) {
    if (typeContainsAnyOrUnknown(checker, indexType, seen)) {
      cache.set(type, true);
      return true;
    }
  }
  for (const property of checker.getPropertiesOfType(type)) {
    const declaration = property.valueDeclaration ?? property.declarations?.[0];
    if (
      declaration &&
      typeContainsAnyOrUnknown(
        checker,
        checker.getTypeOfSymbolAtLocation(property, declaration),
        seen,
      )
    ) {
      cache.set(type, true);
      return true;
    }
  }
  for (const signature of [
    ...checker.getSignaturesOfType(type, ts.SignatureKind.Call),
    ...checker.getSignaturesOfType(type, ts.SignatureKind.Construct),
  ]) {
    if (
      typeContainsAnyOrUnknown(
        checker,
        checker.getReturnTypeOfSignature(signature),
        seen,
      )
    ) {
      cache.set(type, true);
      return true;
    }
    for (const parameter of signature.getParameters()) {
      const declaration =
        parameter.valueDeclaration ?? parameter.declarations?.[0];
      if (
        declaration &&
        typeContainsAnyOrUnknown(
          checker,
          checker.getTypeOfSymbolAtLocation(parameter, declaration),
          seen,
        )
      ) {
        cache.set(type, true);
        return true;
      }
    }
  }
  cache.set(type, false);
  return false;
}

function typeNodeContainsAnyOrUnknown(checker, node) {
  return typeContainsAnyOrUnknown(checker, checker.getTypeFromTypeNode(node));
}

function isGeneratedToneMapTarget(checker, typeNode, governedPaths) {
  return (
    ts.isTypeReferenceNode(typeNode) &&
    typeNode.typeArguments?.length === 2 &&
    ts.isIndexedAccessTypeNode(typeNode.typeArguments[0]) &&
    isGeneratedClosedInputType(
      checker,
      typeNode.typeArguments[0],
      governedPaths,
    ) &&
    isAtlasBadgeToneType(checker, typeNode.typeArguments[1])
  );
}

function isExhaustiveGeneratedToneMap(checker, typeNode, governedPaths) {
  const recordSymbol = ts.isTypeReferenceNode(typeNode)
    ? symbolIdentity(checker, typeNode.typeName)
    : undefined;
  const recordDeclarations = recordSymbol?.declarations ?? [];
  const isStandardRecord =
    recordDeclarations.length === 1 &&
    recordDeclarations.every(
      (declaration) =>
        ts.isTypeAliasDeclaration(declaration) &&
        declaration.name.text === "Record" &&
        declaration.getSourceFile().hasNoDefaultLib &&
        /\/typescript\/lib\/lib\.es5\.d\.ts$/u.test(
          declaration.getSourceFile().fileName.split(path.sep).join("/"),
        ),
    );
  return (
    isStandardRecord &&
    isGeneratedToneMapTarget(checker, typeNode, governedPaths)
  );
}

function authorityEscapeSite(sourceFile, node, pathOf, construct, target) {
  const location = sourceFile.getLineAndCharacterOfPosition(
    node.getStart(sourceFile),
  );
  return {
    path: pathOf(sourceFile),
    line: location.line + 1,
    column: location.character + 1,
    construct,
    target,
    siteSha256: textSha256(node.getText(sourceFile)),
  };
}

function directiveEscapeSites(sourceFile, pathOf) {
  const sites = [];
  const addDirective = (range, construct, target) => {
    const text = sourceFile.text.slice(range.pos, range.end);
    const location = sourceFile.getLineAndCharacterOfPosition(range.pos);
    sites.push({
      path: pathOf(sourceFile),
      line: location.line + 1,
      column: location.character + 1,
      construct,
      target,
      siteSha256: textSha256(text),
    });
  };
  for (const directive of sourceFile.commentDirectives ?? []) {
    if (directive.type === ts.CommentDirectiveType.Ignore) {
      addDirective(directive.range, "ts_ignore", "@ts-ignore");
    } else if (directive.type === ts.CommentDirectiveType.ExpectError) {
      addDirective(directive.range, "ts_expect_error", "@ts-expect-error");
    }
  }
  const noCheckPragma = sourceFile.pragmas?.get("ts-nocheck");
  const noCheckPragmas = Array.isArray(noCheckPragma)
    ? noCheckPragma
    : noCheckPragma
      ? [noCheckPragma]
      : [];
  for (const pragma of noCheckPragmas) {
    if (pragma.range) {
      addDirective(pragma.range, "ts_nocheck", "@ts-nocheck");
    }
  }
  return sites;
}

function collectAuthorityEscapeFacts(
  program,
  candidates,
  pathOf,
  descriptors,
  generatedDefinitionPaths,
  governanceObjectNames,
) {
  if (!Array.isArray(descriptors) || descriptors.length === 0) {
    return {
      authorityPathFiles: [],
      authorityEscapeSites: [],
      authorityIssuerFacts: emptyAuthorityIssuerFacts(),
    };
  }
  const checker = program.getTypeChecker();
  const sourceByPath = new Map(
    program
      .getSourceFiles()
      .map((sourceFile) => [relativePath(sourceFile.fileName), sourceFile]),
  );
  const brandSymbols = new Set();
  const issuerPaths = new Set();
  for (const descriptor of descriptors) {
    const sourceFile = sourceByPath.get(descriptor.componentDeclarationPath);
    if (!sourceFile) continue;
    issuerPaths.add(descriptor.componentDeclarationPath);
    const propType = componentPropType(checker, sourceFile, descriptor);
    collectBrandsInType(checker, propType, brandSymbols);
  }
  for (const brand of brandSymbols) {
    for (const declaration of brand.declarations ?? []) {
      const brandPath = declarationPath(declaration);
      if (brandPath) issuerPaths.add(brandPath);
    }
  }
  for (const issuerPath of [...issuerPaths]) {
    const sourceFile = sourceByPath.get(issuerPath);
    if (!sourceFile) continue;
    const visitBrands = (node) => {
      if (ts.isPropertySignature(node) || ts.isPropertyDeclaration(node)) {
        const brand = privateUniqueBrandSymbol(checker, node);
        if (brand) brandSymbols.add(brand);
      }
      ts.forEachChild(node, visitBrands);
    };
    visitBrands(sourceFile);
  }
  for (const brand of brandSymbols) {
    for (const declaration of brand.declarations ?? []) {
      const brandPath = declarationPath(declaration);
      if (brandPath) issuerPaths.add(brandPath);
    }
  }
  const governedPaths = new Set(generatedDefinitionPaths ?? []);
  const authorityIssuerFacts = collectAuthorityIssuerFacts(
    checker,
    sourceByPath,
    brandSymbols,
    generatedDefinitionPaths,
  );

  const familySymbols = new Set();
  for (const issuerPath of issuerPaths) {
    const sourceFile = sourceByPath.get(issuerPath);
    if (!sourceFile) continue;
    for (const symbol of moduleExports(checker, sourceFile)) {
      const declaration = symbol.valueDeclaration ?? symbol.declarations?.[0];
      if (!declaration) continue;
      const valueType = checker.getTypeOfSymbolAtLocation(symbol, declaration);
      const declaredType =
        (symbol.flags & ts.SymbolFlags.Type) !== 0
          ? checker.getDeclaredTypeOfSymbol(symbol)
          : null;
      if (
        typeTouchesAuthorityBrand(checker, valueType, brandSymbols) ||
        typeTouchesAuthorityBrand(checker, declaredType, brandSymbols)
      ) {
        familySymbols.add(symbol);
      }
    }
  }

  const componentNames = new Set(descriptors.map((item) => item.component));
  const objectNames = new Set(governanceObjectNames ?? []);
  const pathRows = [];
  const authoritySources = [];
  for (const sourceFile of candidates) {
    const relative = pathOf(sourceFile);
    const edges = [];
    if (issuerPaths.has(relative)) edges.push("issuer_declaration");
    if (
      moduleExports(checker, sourceFile).some((symbol) =>
        familySymbols.has(symbol),
      )
    ) {
      edges.push("authority_reexport");
    }
    if (sourceImportsAuthorityFamily(checker, sourceFile, familySymbols)) {
      edges.push("authority_import");
    }
    if (hasAuthorityGovernanceEdge(sourceFile, componentNames, objectNames)) {
      edges.push("governance_owner");
    }
    if (edges.length === 0) continue;
    authoritySources.push(sourceFile);
    pathRows.push({
      path: relative,
      edges: [...new Set(edges)].sort(),
      sourceSha256: textSha256(sourceFile.text),
    });
  }

  const sites = [];
  for (const sourceFile of authoritySources) {
    sites.push(...directiveEscapeSites(sourceFile, pathOf));
    const visit = (node) => {
      if (ts.isAsExpression(node) || ts.isTypeAssertionExpression(node)) {
        sites.push(
          authorityEscapeSite(
            sourceFile,
            node,
            pathOf,
            ts.isAsExpression(node) ? "as_assertion" : "type_assertion",
            node.type.getText(sourceFile),
          ),
        );
      } else if (node.kind === ts.SyntaxKind.AnyKeyword) {
        sites.push(
          authorityEscapeSite(sourceFile, node, pathOf, "explicit_any", "any"),
        );
      } else if (ts.isSatisfiesExpression(node)) {
        const targetType = checker.getTypeFromTypeNode(node.type);
        const proof = terminalTypeDeclarationPaths(checker, node.type);
        const isGeneratedConformance =
          proof.complete &&
          proof.paths.size > 0 &&
          [...proof.paths].every((candidatePath) =>
            governedPaths.has(candidatePath),
          );
        let safety = "unrelated_conformance";
        if (isExhaustiveGeneratedToneMap(checker, node.type, governedPaths)) {
          safety = "exhaustive_generated_record";
        } else if (
          isGeneratedToneMapTarget(checker, node.type, governedPaths)
        ) {
          safety = "unsafe_exhaustiveness_lookalike";
        } else if (isGeneratedConformance) {
          safety = "generated_conformance";
        } else if (typeNodeContainsAnyOrUnknown(checker, node.type)) {
          safety = "unsafe_widening";
        } else if (
          typeTouchesAuthorityBrand(checker, targetType, brandSymbols)
        ) {
          safety = "unsafe_brand";
        }
        sites.push({
          ...authorityEscapeSite(
            sourceFile,
            node,
            pathOf,
            "satisfies",
            node.type.getText(sourceFile),
          ),
          safety,
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  const sortKey = (item) =>
    `${item.path}:${String(item.line ?? 0).padStart(8, "0")}:${String(item.column ?? 0).padStart(8, "0")}:${item.construct ?? ""}`;
  return {
    authorityPathFiles: pathRows.sort((left, right) =>
      left.path.localeCompare(right.path),
    ),
    authorityEscapeSites: sites.sort((left, right) =>
      sortKey(left).localeCompare(sortKey(right)),
    ),
    authorityIssuerFacts,
  };
}

function collectProgramFacts(
  program,
  protectedDefinitions = [],
  generatedDefinitionPaths = [],
  authorityPropDescriptors = [],
  authorityPathDescriptors = [],
  authorityGovernanceObjects = [],
) {
  const checker = program.getTypeChecker();
  const definitions = [];
  const authorityCandidates = [];
  const authorityCandidateKeys = new Set();
  const definitionNodes = new Set();
  const definitionSources = program
    .getSourceFiles()
    .filter((sourceFile) => isDefinitionSource(sourceFile.fileName));
  const statusInventorySources = definitionSources.filter((sourceFile) =>
    isDashboardStatusInventorySource(sourceFile.fileName),
  );

  for (const sourceFile of statusInventorySources) {
    const visit = (node) => {
      const constFact = constVocabularyFact(
        node,
        sourceFile,
        relativePath(sourceFile.fileName),
      );
      if (constFact) {
        const key = JSON.stringify(constFact);
        if (!authorityCandidateKeys.has(key)) {
          authorityCandidateKeys.add(key);
          authorityCandidates.push(constFact);
        }
      }
      const returnFact = semanticReturnFact(
        node,
        sourceFile,
        relativePath(sourceFile.fileName),
      );
      if (returnFact) {
        const key = JSON.stringify(returnFact);
        if (!authorityCandidateKeys.has(key)) {
          authorityCandidateKeys.add(key);
          authorityCandidates.push(returnFact);
        }
      }
      if (
        (ts.isTypeAliasDeclaration(node) || ts.isEnumDeclaration(node)) &&
        semanticName(node.name.text)
      ) {
        const candidateMembers = ts.isTypeAliasDeclaration(node)
          ? (stringUnionMembers(node.type) ?? [])
          : enumMembers(node);
        if (candidateMembers.length > 0) {
          const candidate = {
            kind: "named",
            path: relativePath(sourceFile.fileName),
            startLine: lineOf(sourceFile, node),
            endLine: endLineOf(sourceFile, node),
            declarationName: node.name.text,
            fieldName: null,
            members: candidateMembers,
            typeExpression: ts.isTypeAliasDeclaration(node)
              ? node.type.getText(sourceFile)
              : node.getText(sourceFile),
          };
          const key = JSON.stringify(candidate);
          if (!authorityCandidateKeys.has(key)) {
            authorityCandidateKeys.add(key);
            authorityCandidates.push(candidate);
          }
        }
      }
      if (
        (ts.isTypeAliasDeclaration(node) ||
          ts.isEnumDeclaration(node) ||
          ts.isInterfaceDeclaration(node)) &&
        node.name.text.endsWith("Status")
      ) {
        const members = ts.isTypeAliasDeclaration(node)
          ? (stringUnionMembers(node.type) ?? [])
          : ts.isEnumDeclaration(node)
            ? enumMembers(node)
            : [];
        const nameNode = node.name;
        definitionNodes.add(nameNode);
        definitions.push({
          kind: "named",
          path: relativePath(sourceFile.fileName),
          startLine: lineOf(sourceFile, node),
          endLine: endLineOf(sourceFile, node),
          declarationName: node.name.text,
          fieldName: null,
          members,
          typeExpression: ts.isTypeAliasDeclaration(node)
            ? node.type.getText(sourceFile)
            : node.getText(sourceFile),
          symbol: symbolIdentity(checker, nameNode),
          symbolNode: nameNode,
        });
      }

      const members = stringUnionMembers(node);
      const owner = members ? inlineOwner(node) : null;
      if (owner && semanticName(owner.fieldName ?? "")) {
        const candidate = {
          kind: "inline",
          path: relativePath(sourceFile.fileName),
          startLine: lineOf(sourceFile, owner.declaration),
          endLine: endLineOf(sourceFile, owner.declaration),
          declarationName: null,
          fieldName: owner.fieldName,
          members,
          typeExpression: node.getText(sourceFile),
        };
        const key = JSON.stringify(candidate);
        if (!authorityCandidateKeys.has(key)) {
          authorityCandidateKeys.add(key);
          authorityCandidates.push(candidate);
        }
      }
      if (owner && isInlineStatusField(owner.fieldName)) {
        const nameNode = owner.declaration.name;
        definitionNodes.add(nameNode);
        definitions.push({
          kind: "inline",
          path: relativePath(sourceFile.fileName),
          startLine: lineOf(sourceFile, owner.declaration),
          endLine: endLineOf(sourceFile, owner.declaration),
          declarationName: null,
          fieldName: owner.fieldName,
          members,
          typeExpression: node.getText(sourceFile),
          symbol: symbolIdentity(checker, nameNode),
          symbolNode: nameNode,
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  for (const definition of definitions) {
    const consumers = new Map();
    if (definition.symbol) {
      for (const sourceFile of program.getSourceFiles()) {
        const relative = relativePath(sourceFile.fileName);
        if (!relative.startsWith("apps/runtime-dashboard/")) continue;
        const visit = (node) => {
          if (
            (ts.isIdentifier(node) || ts.isStringLiteral(node)) &&
            !definitionNodes.has(node) &&
            symbolIdentity(checker, node) === definition.symbol
          ) {
            const line = lineOf(sourceFile, node);
            const key = `${relative}:${line}`;
            consumers.set(key, {
              path: relative,
              line,
              kind: consumerKind(sourceFile, node),
            });
          }
          ts.forEachChild(node, visit);
        };
        visit(sourceFile);
      }
    }
    definition.consumers = [...consumers.values()].sort((left, right) =>
      `${left.path}:${String(left.line).padStart(8, "0")}`.localeCompare(
        `${right.path}:${String(right.line).padStart(8, "0")}`,
      ),
    );
    delete definition.symbol;
    delete definition.symbolNode;
  }
  const statusOwnership = statusInventorySources.find(
    (sourceFile) =>
      relativePath(sourceFile.fileName) ===
      "apps/runtime-dashboard/src/shared/lib/domain/statusOwnership.ts",
  );
  let factorySymbol;
  let sinkSymbol;
  if (statusOwnership) {
    for (const statement of statusOwnership.statements) {
      if (!ts.isFunctionDeclaration(statement) || !statement.name) continue;
      if (statement.name.text === "createInteractionState") {
        factorySymbol = symbolIdentity(checker, statement.name);
      }
      if (statement.name.text === "presentAuthority") {
        sinkSymbol = symbolIdentity(checker, statement.name);
      }
    }
  }
  const interactionLeaks = collectInteractionLeaks(statusInventorySources, {
    binding(node) {
      if (!ts.isIdentifier(node) && !ts.isPropertyAccessExpression(node)) {
        return undefined;
      }
      return symbolIdentity(checker, node);
    },
    isFactory(node) {
      return (
        factorySymbol !== undefined &&
        symbolIdentity(checker, node) === factorySymbol
      );
    },
    isSink(node) {
      return (
        sinkSymbol !== undefined && symbolIdentity(checker, node) === sinkSymbol
      );
    },
    path(sourceFile) {
      return relativePath(sourceFile.fileName);
    },
  });
  const protectedRevivals = collectProtectedRevivals(
    statusInventorySources,
    protectedDefinitions,
    (sourceFile) => relativePath(sourceFile.fileName),
    checker,
    new Set(generatedDefinitionPaths),
  );
  const authorityEscapeFacts = collectAuthorityEscapeFacts(
    program,
    program.getSourceFiles().filter((sourceFile) => {
      const relative = relativePath(sourceFile.fileName);
      return (
        relative.startsWith("apps/runtime-dashboard/src/") ||
        relative.startsWith("packages/atlas-ui/src/") ||
        relative.startsWith("packages/atlas-ui/tests/")
      );
    }),
    (sourceFile) => relativePath(sourceFile.fileName),
    authorityPathDescriptors,
    generatedDefinitionPaths,
    authorityGovernanceObjects,
  );
  const capabilityDiscoveryFacts = {
    productionFiles: statusInventorySources.length,
    ...collectCapabilityDiscoveryFacts(
      statusInventorySources,
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
    ),
  };
  const offlineQueueProductionSources = statusInventorySources.filter(
    (sourceFile) => isOfflineQueueProductionSource(sourceFile.fileName),
  );
  const offlineQueueFacts = collectOfflineQueueFacts(
    offlineQueueProductionSources,
    (sourceFile) => relativePath(sourceFile.fileName),
  );
  offlineQueueFacts.definitionFiles = statusInventorySources.length;
  offlineQueueFacts.nonTypeScriptDefinitionFiles = statusInventorySources
    .filter((sourceFile) => !/\.tsx?$/.test(relativePath(sourceFile.fileName)))
    .map((sourceFile) => relativePath(sourceFile.fileName))
    .sort();
  return {
    authorityCandidates,
    definitions,
    interactionLeaks,
    protectedRevivals,
    sourceDenominators: {
      atlasUiProduction: definitionSources.filter((sourceFile) =>
        relativePath(sourceFile.fileName).startsWith("packages/atlas-ui/src/"),
      ).length,
      dashboardProduction: definitionSources.filter((sourceFile) =>
        relativePath(sourceFile.fileName).startsWith(
          "apps/runtime-dashboard/src/",
        ),
      ).length,
    },
    authoritySinkDeclarations: collectAuthoritySinkDeclarations(
      definitionSources,
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
    ),
    badgeSites: collectDirectBadgeSites(
      definitionSources,
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
    ),
    authorityPropCensus: collectAuthorityPropCensus(
      definitionSources,
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
      authorityPropDescriptors,
    ),
    capabilityDiscoveryFacts,
    offlineQueueFacts,
    queryCachePolicyFacts: collectQueryCachePolicyFacts(
      program.getSourceFiles(),
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
    ),
    persistenceConstructionFacts: collectPersistenceConstructionFacts(
      program,
      checker,
    ),
    ...authorityEscapeFacts,
  };
}

function overrideInteractionIdentities(sourceFile, relative) {
  const factoryBindings = new Set();
  const sinkBindings = new Set();
  const namespaceBindings = new Set();
  const key = (name) => `${relative}:${name}`;
  for (const statement of sourceFile.statements) {
    if (
      !ts.isImportDeclaration(statement) ||
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      !statement.moduleSpecifier.text.endsWith("statusOwnership") ||
      !statement.importClause?.namedBindings
    ) {
      continue;
    }
    const bindings = statement.importClause.namedBindings;
    if (ts.isNamespaceImport(bindings)) {
      namespaceBindings.add(bindings.name.text);
      continue;
    }
    for (const element of bindings.elements) {
      const imported = element.propertyName?.text ?? element.name.text;
      if (imported === "createInteractionState") {
        factoryBindings.add(key(element.name.text));
      }
      if (imported === "presentAuthority") {
        sinkBindings.add(key(element.name.text));
      }
    }
  }
  const matchesNamespaceMember = (node, member) => {
    const current = unwrapExpression(node);
    return (
      ts.isPropertyAccessExpression(current) &&
      ts.isIdentifier(current.expression) &&
      namespaceBindings.has(current.expression.text) &&
      current.name.text === member
    );
  };
  return {
    binding(node) {
      const current = unwrapExpression(node);
      if (ts.isIdentifier(current)) return key(current.text);
      if (ts.isPropertyAccessExpression(current)) {
        return key(current.getText(sourceFile));
      }
      return undefined;
    },
    isFactory(node) {
      const current = unwrapExpression(node);
      return (
        (ts.isIdentifier(current) && factoryBindings.has(key(current.text))) ||
        matchesNamespaceMember(current, "createInteractionState")
      );
    },
    isSink(node) {
      const current = unwrapExpression(node);
      return (
        (ts.isIdentifier(current) && sinkBindings.has(key(current.text))) ||
        matchesNamespaceMember(current, "presentAuthority")
      );
    },
    path() {
      return relative;
    },
  };
}

function createOverrideProgram(
  overrides,
  includeDashboardProgramRoots = false,
) {
  const sources = new Map(
    Object.entries(overrides).map(([relative, source]) => [
      path.resolve(repoRoot, relative),
      source,
    ]),
  );
  const configPath = path.join(dashboardRoot, "tsconfig.app.json");
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error) {
    throw new Error(
      ts.flattenDiagnosticMessageText(config.error.messageText, "\n"),
    );
  }
  const parsed = ts.parseJsonConfigFileContent(
    config.config,
    ts.sys,
    dashboardRoot,
  );
  const options = { ...parsed.options, noEmit: true, types: [] };
  const host = ts.createCompilerHost(options, true);
  const defaultFileExists = host.fileExists.bind(host);
  const defaultGetSourceFile = host.getSourceFile.bind(host);
  const defaultReadFile = host.readFile.bind(host);
  const canonical = (fileName) => path.resolve(fileName);
  host.fileExists = (fileName) =>
    sources.has(canonical(fileName)) || defaultFileExists(fileName);
  host.readFile = (fileName) =>
    sources.get(canonical(fileName)) ?? defaultReadFile(fileName);
  host.getSourceFile = (
    fileName,
    languageVersion,
    onError,
    shouldCreateNewSourceFile,
  ) => {
    const source = sources.get(canonical(fileName));
    return source === undefined
      ? defaultGetSourceFile(
          fileName,
          languageVersion,
          onError,
          shouldCreateNewSourceFile,
        )
      : ts.createSourceFile(
          fileName,
          source,
          ts.ScriptTarget.Latest,
          true,
          fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
        );
  };
  return ts.createProgram({
    host,
    options,
    rootNames: includeDashboardProgramRoots
      ? [...new Set([...parsed.fileNames, ...sources.keys()])]
      : [...sources.keys()],
  });
}

function collectOverrideFacts(
  overrides,
  protectedDefinitions = [],
  generatedDefinitionPaths = [],
  validateOverrideDiagnostics = false,
  authorityPropDescriptors = [],
  authorityPathDescriptors = [],
  authorityGovernanceObjects = [],
  includeDashboardProgramRoots = false,
) {
  const facts = {
    authorityCandidates: [],
    definitions: [],
    interactionLeaks: [],
    protectedRevivals: [],
    authoritySinkDeclarations: [],
    badgeSites: [],
    authorityPropCensus: [],
    authorityPathFiles: [],
    authorityEscapeSites: [],
    authorityIssuerFacts: emptyAuthorityIssuerFacts(),
    capabilityDiscoveryFacts: {
      productionFiles: 0,
      issuerCalls: [],
      featureLiterals: [],
    },
  };
  const program = createOverrideProgram(
    overrides,
    includeDashboardProgramRoots,
  );
  if (validateOverrideDiagnostics) {
    const overridePaths = new Set(
      Object.keys(overrides).map((relative) =>
        path.resolve(repoRoot, relative),
      ),
    );
    facts.overrideDiagnostics = [
      ...program.getSyntacticDiagnostics(),
      ...program.getSemanticDiagnostics(),
    ]
      .filter(
        (diagnostic) =>
          diagnostic.file &&
          overridePaths.has(path.resolve(diagnostic.file.fileName)),
      )
      .map((diagnostic) => {
        const location = diagnostic.file.getLineAndCharacterOfPosition(
          diagnostic.start ?? 0,
        );
        return {
          path: relativePath(diagnostic.file.fileName),
          line: location.line + 1,
          column: location.character + 1,
          code: diagnostic.code,
          message: ts
            .flattenDiagnosticMessageText(diagnostic.messageText, " ")
            .split(`${repoRoot}${path.sep}`)
            .join(""),
        };
      })
      .sort((left, right) =>
        `${left.path}:${String(left.line).padStart(8, "0")}:${String(left.column).padStart(8, "0")}:${left.code}:${left.message}`.localeCompare(
          `${right.path}:${String(right.line).padStart(8, "0")}:${String(right.column).padStart(8, "0")}:${right.code}:${right.message}`,
        ),
      );
  }
  const checker = program.getTypeChecker();
  const sourceFiles = [];
  for (const relative of Object.keys(overrides)) {
    const sourceFile = program.getSourceFile(path.resolve(repoRoot, relative));
    if (!sourceFile) throw new Error(`missing override source: ${relative}`);
    sourceFiles.push(sourceFile);
    const visit = (node) => {
      const constFact = constVocabularyFact(node, sourceFile, relative);
      if (constFact) {
        facts.authorityCandidates.push(constFact);
      }
      const returnFact = semanticReturnFact(node, sourceFile, relative);
      if (returnFact) {
        facts.authorityCandidates.push(returnFact);
      }
      if (ts.isTypeAliasDeclaration(node) || ts.isEnumDeclaration(node)) {
        const members = ts.isTypeAliasDeclaration(node)
          ? (stringUnionMembers(node.type) ?? [])
          : enumMembers(node);
        if (
          members.length > 0 &&
          (semanticName(node.name.text) || members.length > 1)
        ) {
          facts.definitions.push({
            kind: "named",
            path: relative,
            startLine: lineOf(sourceFile, node),
            declarationName: node.name.text,
            fieldName: null,
            members,
          });
        }
        if (members.length > 0 && semanticName(node.name.text)) {
          facts.authorityCandidates.push({
            kind: "named",
            path: relative,
            startLine: lineOf(sourceFile, node),
            endLine: endLineOf(sourceFile, node),
            declarationName: node.name.text,
            fieldName: null,
            members,
            typeExpression: ts.isTypeAliasDeclaration(node)
              ? node.type.getText(sourceFile)
              : node.getText(sourceFile),
          });
        }
      }
      const members = stringUnionMembers(node);
      const owner = members ? inlineOwner(node) : null;
      if (owner && semanticName(owner.fieldName ?? "")) {
        facts.authorityCandidates.push({
          kind: "inline",
          path: relative,
          startLine: lineOf(sourceFile, owner.declaration),
          endLine: endLineOf(sourceFile, owner.declaration),
          declarationName: null,
          fieldName: owner.fieldName,
          members,
          typeExpression: node.getText(sourceFile),
        });
        facts.definitions.push({
          kind: "inline",
          path: relative,
          startLine: lineOf(sourceFile, owner.declaration),
          declarationName: null,
          fieldName: owner.fieldName,
          members,
        });
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
    facts.interactionLeaks.push(
      ...collectInteractionLeaks(
        [sourceFile],
        overrideInteractionIdentities(sourceFile, relative),
      ),
    );
  }
  facts.protectedRevivals.push(
    ...collectProtectedRevivals(
      sourceFiles,
      protectedDefinitions,
      (sourceFile) => relativePath(sourceFile.fileName),
      checker,
      new Set(generatedDefinitionPaths),
    ),
  );
  facts.authoritySinkDeclarations.push(
    ...collectAuthoritySinkDeclarations(sourceFiles, checker, (sourceFile) =>
      relativePath(sourceFile.fileName),
    ),
  );
  facts.badgeSites.push(
    ...collectDirectBadgeSites(sourceFiles, checker, (sourceFile) =>
      relativePath(sourceFile.fileName),
    ),
  );
  facts.authorityPropCensus.push(
    ...collectAuthorityPropCensus(
      sourceFiles,
      checker,
      (sourceFile) => relativePath(sourceFile.fileName),
      authorityPropDescriptors,
    ),
  );
  const authorityEscapeFacts = collectAuthorityEscapeFacts(
    program,
    sourceFiles,
    (sourceFile) => relativePath(sourceFile.fileName),
    authorityPathDescriptors,
    generatedDefinitionPaths,
    authorityGovernanceObjects,
  );
  facts.authorityPathFiles.push(...authorityEscapeFacts.authorityPathFiles);
  facts.authorityEscapeSites.push(...authorityEscapeFacts.authorityEscapeSites);
  facts.authorityIssuerFacts = authorityEscapeFacts.authorityIssuerFacts;
  facts.capabilityDiscoveryFacts = {
    productionFiles: sourceFiles.length,
    ...collectCapabilityDiscoveryFacts(sourceFiles, checker, (sourceFile) =>
      relativePath(sourceFile.fileName),
    ),
  };
  const offlineQueueDefinitionSources = includeDashboardProgramRoots
    ? program
        .getSourceFiles()
        .filter((sourceFile) =>
          isDashboardStatusInventorySource(sourceFile.fileName),
        )
    : sourceFiles.filter((sourceFile) =>
        isDashboardStatusInventorySource(sourceFile.fileName),
      );
  facts.offlineQueueFacts = collectOfflineQueueFacts(
    offlineQueueDefinitionSources.filter((sourceFile) =>
      isOfflineQueueProductionSource(sourceFile.fileName),
    ),
    (sourceFile) => relativePath(sourceFile.fileName),
  );
  facts.offlineQueueFacts.definitionFiles =
    offlineQueueDefinitionSources.length;
  facts.offlineQueueFacts.nonTypeScriptDefinitionFiles =
    offlineQueueDefinitionSources
      .filter(
        (sourceFile) => !/\.tsx?$/.test(relativePath(sourceFile.fileName)),
      )
      .map((sourceFile) => relativePath(sourceFile.fileName))
      .sort();
  facts.queryCachePolicyFacts = collectQueryCachePolicyFacts(
    [...program.getSourceFiles()],
    checker,
    (sourceFile) => relativePath(sourceFile.fileName),
  );
  facts.persistenceConstructionFacts = collectPersistenceConstructionFacts(
    program,
    checker,
  );
  return facts;
}

function parseConfig(configPath, root) {
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error) {
    throw new Error(
      ts.flattenDiagnosticMessageText(config.error.messageText, "\n"),
    );
  }
  return ts.parseJsonConfigFileContent(config.config, ts.sys, root);
}

let input = "";
for await (const chunk of process.stdin) input += chunk;
const request = input.trim() ? JSON.parse(input) : {};

if (request.sourceOverrides) {
  process.stdout.write(
    JSON.stringify(
      collectOverrideFacts(
        request.sourceOverrides,
        request.protectedDefinitions,
        request.generatedDefinitionPaths,
        request.validateOverrideDiagnostics === true,
        request.authorityPropDescriptors,
        request.authorityPathDescriptors,
        request.authorityGovernanceObjects,
        request.includeDashboardProgramRoots === true,
      ),
    ),
  );
} else {
  const parsed = parseConfig(
    path.join(dashboardRoot, "tsconfig.app.json"),
    dashboardRoot,
  );
  const atlasUiParsed = parseConfig(
    path.join(atlasUiRoot, "tsconfig.json"),
    atlasUiRoot,
  );
  const program = ts.createProgram({
    rootNames: [...new Set([...parsed.fileNames, ...atlasUiParsed.fileNames])],
    options: parsed.options,
  });
  process.stdout.write(
    JSON.stringify(
      collectProgramFacts(
        program,
        request.protectedDefinitions,
        request.generatedDefinitionPaths,
        request.authorityPropDescriptors,
        request.authorityPathDescriptors,
        request.authorityGovernanceObjects,
      ),
    ),
  );
}
