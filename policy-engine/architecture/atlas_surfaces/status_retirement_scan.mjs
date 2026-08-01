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

function isGeneratedClosedInputType(checker, typeNode) {
  const root = typeRootSymbol(checker, typeNode);
  if (
    !symbolDeclarationsResolveUnder(root, "packages/runtime-api-client/")
  ) {
    return false;
  }
  return isClosedStringLiteralType(checker.getTypeFromTypeNode(typeNode));
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
    if (
      ts.isElementAccessExpression(current) &&
      current.argumentExpression
    ) {
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

function isAuthorizedBadgeToneProjection(checker, node, parameters) {
  return (
    parameters.length > 0 &&
    isAtlasBadgeToneType(checker, node.type) &&
    parameters.every(
      (parameter) =>
        parameter.type &&
        isGeneratedClosedInputType(checker, parameter.type),
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
    type.isUnion?.() && type.types.some((member) => typeCanCarryOpenLabel(member)),
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
        ) && typeCanCarryOpenLabel(checker.getTypeAtLocation(current))
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
        current.expression && expressionIsOwnerDerived(current.expression, seen),
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
      return names.length === 1
        ? symbolIdentity(checker, names[0])
        : undefined;
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
      isAuthorizedBadgeToneProjection(checker, node, parameters);
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
    for (const relation of [...spreadSourceRelations, ...objectAliasRelations]) {
      for (const [name, source] of
        objectFunctionSources.get(relation.source) ?? []) {
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
      let controls = projectedFunctions.get(callee) ?? transparentFunctions.get(callee);
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
        changed = addBindingSymbols(checker, node.name, projectedValues) || changed;
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
          [
            ts.SyntaxKind.PlusPlusToken,
            ts.SyntaxKind.MinusMinusToken,
          ].includes(current.operator)) ||
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

function collectProgramFacts(program, protectedDefinitions = []) {
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
  const protectedRevivals = collectProtectedRevivals(
    definitionSources,
    protectedDefinitions,
    (sourceFile) => relativePath(sourceFile.fileName),
    checker,
  );
  return {
    authorityCandidates,
    definitions,
    interactionLeaks,
    protectedRevivals,
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

function createOverrideProgram(overrides) {
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
    rootNames: [...sources.keys()],
  });
}

function collectOverrideFacts(overrides, protectedDefinitions = []) {
  const facts = {
    authorityCandidates: [],
    definitions: [],
    interactionLeaks: [],
    protectedRevivals: [],
  };
  const program = createOverrideProgram(overrides);
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
    ),
  );
  return facts;
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
      ),
    ),
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
  process.stdout.write(
    JSON.stringify(collectProgramFacts(program, request.protectedDefinitions)),
  );
}
