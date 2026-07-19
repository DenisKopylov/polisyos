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
    if (!ts.isLiteralTypeNode(member) || !ts.isStringLiteral(member.literal)) {
      return null;
    }
    members.push(member.literal.text);
  }
  return [...new Set(members)].sort();
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
  return /(?:status|state|verdict|grade|disposition|freshness|readiness|authority|closure|verification|dispute|evidence|terminal|admissib|publishab|support)/iu.test(
    name,
  );
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

  for (const sourceFile of program.getSourceFiles()) {
    if (!isDefinitionSource(sourceFile.fileName)) continue;
    const visit = (node) => {
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
  return { authorityCandidates, definitions };
}

function collectOverrideFacts(overrides) {
  const facts = {
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
    const interactionBindings = new Set();
    const visit = (node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
        if (
          node.initializer &&
          ts.isCallExpression(node.initializer) &&
          node.initializer.expression.getText(sourceFile) ===
            "createInteractionState"
        ) {
          interactionBindings.add(node.name.text);
        }
      }
      if (
        ts.isCallExpression(node) &&
        node.expression.getText(sourceFile) === "presentAuthority" &&
        node.arguments.some(
          (argument) =>
            ts.isIdentifier(argument) && interactionBindings.has(argument.text),
        )
      ) {
        facts.interactionLeaks.push({
          path: relative,
          line: lineOf(sourceFile, node),
        });
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
      }
      const members = stringUnionMembers(node);
      const owner = members ? inlineOwner(node) : null;
      if (owner && semanticName(owner.fieldName ?? "")) {
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
