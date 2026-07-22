#!/usr/bin/env node

import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const dashboardRoot = path.resolve(process.cwd(), "apps/runtime-dashboard");
const repoRoot = process.cwd();
const require = createRequire(path.join(dashboardRoot, "package.json"));
const ts = require("typescript");

function relativePath(fileName) {
  return path.relative(repoRoot, fileName).split(path.sep).join("/");
}

function isGeneratedDefinitionSource(fileName) {
  return relativePath(fileName) === "apps/runtime-dashboard/src/api/types.ts";
}

function isDefinitionSource(fileName) {
  const relative = relativePath(fileName);
  return (
    relative.startsWith("apps/runtime-dashboard/src/") &&
    !isGeneratedDefinitionSource(fileName) &&
    !/\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$|\.stories\.[cm]?tsx?$/.test(
      relative,
    )
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

function collectProgramFacts(program) {
  const checker = program.getTypeChecker();
  const definitions = [];
  const authorityCandidates = [];
  const authorityCandidateKeys = new Set();
  const definitionNodes = new Set();
  const definitionSources = program
    .getSourceFiles()
    .filter((sourceFile) => isDefinitionSource(sourceFile.fileName));

  for (const sourceFile of definitionSources) {
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
  const statusOwnership = definitionSources.find(
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
  const interactionLeaks = collectInteractionLeaks(definitionSources, {
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
  return { authorityCandidates, definitions, interactionLeaks };
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

function collectOverrideFacts(overrides) {
  const facts = {
    authorityCandidates: [],
    definitions: [],
    interactionLeaks: [],
  };
  for (const [relative, source] of Object.entries(overrides)) {
    const sourceFile = ts.createSourceFile(
      relative,
      source,
      ts.ScriptTarget.Latest,
      true,
      relative.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
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
  return facts;
}

let input = "";
for await (const chunk of process.stdin) input += chunk;
const request = input.trim() ? JSON.parse(input) : {};

if (request.sourceOverrides) {
  process.stdout.write(
    JSON.stringify(collectOverrideFacts(request.sourceOverrides)),
  );
} else {
  const configPath = path.join(dashboardRoot, "tsconfig.app.json");
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error)
    throw new Error(
      ts.flattenDiagnosticMessageText(config.error.messageText, "\n"),
    );
  const parsed = ts.parseJsonConfigFileContent(
    config.config,
    ts.sys,
    dashboardRoot,
  );
  const program = ts.createProgram({
    rootNames: parsed.fileNames,
    options: parsed.options,
  });
  process.stdout.write(JSON.stringify(collectProgramFacts(program)));
}
