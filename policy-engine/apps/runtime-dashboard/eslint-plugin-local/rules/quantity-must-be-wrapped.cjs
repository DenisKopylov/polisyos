"use strict";

const {
  CONTROL_CALLS,
  CONTROL_TOKENS,
  DEBUG_FILE_RE,
  DECISION_TOKENS,
  FORMAT_OPTION_PROPS,
  LAYOUT_PROPS,
  TELEMETRY_TOKENS,
  classifyLine,
  hasAnyToken,
} = require("./quantity-classifier.cjs");

const NON_AUTHORITY_NUMERIC_MODULE = "@/shared/lib/domain/nonAuthorityNumeric";
const NON_AUTHORITY_NUMERIC_IMPORTS = new Map([
  ["interactionControl", "interaction"],
  ["layoutGeometry", "layout"],
  ["motionGeometry", "motion"],
  ["operationalRequestControl", "operational"],
]);

function isNumberLiteral(node) {
  return (
    (node.type === "Literal" && typeof node.value === "number") ||
    (node.type === "NumericLiteral" && typeof node.value === "number")
  );
}

function jsxName(name) {
  if (!name) {
    return null;
  }
  if (name.type === "JSXIdentifier") {
    return name.name;
  }
  if (name.type === "JSXMemberExpression") {
    return jsxName(name.property);
  }
  return null;
}

function isInsideQuantity(node) {
  let cursor = node.parent;
  while (cursor) {
    if (cursor.type === "JSXElement") {
      const tagName = jsxName(
        cursor.openingElement && cursor.openingElement.name,
      );
      if (tagName === "Quantity") {
        return true;
      }
    }
    cursor = cursor.parent;
  }
  return false;
}

function attributeName(node) {
  let cursor = node.parent;
  while (cursor) {
    if (
      cursor.type === "JSXAttribute" &&
      cursor.name &&
      cursor.name.type === "JSXIdentifier"
    ) {
      return cursor.name.name;
    }
    if (cursor.type === "JSXElement") {
      return null;
    }
    cursor = cursor.parent;
  }
  return null;
}

function propertyName(key) {
  if (!key) {
    return null;
  }
  if (key.type === "Identifier") {
    return key.name;
  }
  if (key.type === "Literal") {
    return String(key.value);
  }
  return null;
}

function callName(callee) {
  if (!callee) {
    return null;
  }
  if (callee.type === "Identifier") {
    return callee.name;
  }
  if (callee.type === "MemberExpression") {
    return propertyName(callee.property);
  }
  return null;
}

function nodeText(sourceCode, node) {
  return node ? sourceCode.getText(node) : "";
}

function contextName(node) {
  let cursor = node.parent;
  while (cursor) {
    if (
      cursor.type === "VariableDeclarator" &&
      cursor.id.type === "Identifier"
    ) {
      return cursor.id.name;
    }
    if (cursor.type === "Property" && cursor.key) {
      const name = propertyName(cursor.key);
      if (name) {
        return name;
      }
    }
    if (cursor.type === "JSXExpressionContainer") {
      return attributeName(cursor) ?? "jsx_child";
    }
    cursor = cursor.parent;
  }
  return null;
}

function hasClassificationComment(sourceCode, node) {
  const comments = [
    ...sourceCode.getCommentsBefore(node),
    ...sourceCode.getCommentsInside(node),
  ];
  return comments.some((comment) =>
    /policyos-quantity:\s*(telemetry|layout|debug)/iu.test(comment.value),
  );
}

function isDirectJsxChild(node) {
  let cursor = node;
  while (cursor.parent) {
    if (
      cursor.parent.type === "UnaryExpression" ||
      cursor.parent.type === "TSAsExpression" ||
      cursor.parent.type === "TSSatisfiesExpression"
    ) {
      cursor = cursor.parent;
      continue;
    }
    break;
  }
  return (
    cursor.parent?.type === "JSXExpressionContainer" &&
    cursor.parent.parent?.type !== "JSXAttribute"
  );
}

function hasNamedToken(value, tokens) {
  const words = String(value || "")
    .replace(/([a-z0-9])([A-Z])/gu, "$1 $2")
    .toLowerCase()
    .split(/[^a-z0-9]+/u)
    .filter(Boolean);
  return tokens.some((token) => words.includes(token));
}

function resolvedVariable(sourceCode, node, name) {
  let scope = sourceCode.getScope(node);
  while (scope) {
    const variable = scope.set?.get(name);
    if (variable) {
      return variable;
    }
    scope = scope.upper;
  }
  return null;
}

function canonicalNumericClassification(node, sourceCode, structuralImports) {
  let expression = node;
  if (
    node.parent?.type === "UnaryExpression" &&
    (node.parent.operator === "-" || node.parent.operator === "+")
  ) {
    expression = node.parent;
  }
  const call = expression.parent;
  if (
    call?.type !== "CallExpression" ||
    call.arguments[0] !== expression ||
    call.callee.type !== "Identifier"
  ) {
    return undefined;
  }

  const structuralImport = structuralImports.get(call.callee.name);
  if (!structuralImport) {
    return NON_AUTHORITY_NUMERIC_IMPORTS.has(call.callee.name)
      ? "decision"
      : undefined;
  }
  const binding = resolvedVariable(sourceCode, call, call.callee.name);
  const isCanonicalImport = binding?.defs.some(
    (definition) =>
      definition.type === "ImportBinding" &&
      definition.node === structuralImport.specifier,
  );
  if (!isCanonicalImport) {
    return "decision";
  }
  const { classification } = structuralImport;
  if (isDirectJsxChild(call)) {
    return "decision";
  }

  const propName = attributeName(call);
  const name = contextName(call);
  if (classification === "layout") {
    if (propName && LAYOUT_PROPS.has(propName)) {
      return null;
    }
    if (
      (propName && hasNamedToken(propName, DECISION_TOKENS)) ||
      (name && hasNamedToken(name, DECISION_TOKENS))
    ) {
      return "decision";
    }
  }
  if (
    classification === "motion" &&
    ((propName && hasNamedToken(propName, DECISION_TOKENS)) ||
      (name && hasNamedToken(name, DECISION_TOKENS)))
  ) {
    return "decision";
  }

  return null;
}

function isControlOrFormattingLiteral(node, sourceCode) {
  let cursor = node.parent;
  if (cursor?.type === "UnaryExpression") {
    cursor = cursor.parent;
  }

  if (!cursor) {
    return false;
  }

  if (cursor.type === "CallExpression") {
    const name = callName(cursor.callee);
    if (CONTROL_CALLS.has(name)) {
      return true;
    }
    const argumentIndex = cursor.arguments.indexOf(node);
    if (
      argumentIndex > 0 &&
      ["formatNumber", "formatPercent", "formatCurrency", "t"].includes(name)
    ) {
      return true;
    }
  }

  if (cursor.type === "Property") {
    const name = propertyName(cursor.key);
    if (
      name &&
      (FORMAT_OPTION_PROPS.has(name) || hasAnyToken(name, CONTROL_TOKENS))
    ) {
      return true;
    }
  }

  if (
    cursor.type === "BinaryExpression" ||
    cursor.type === "LogicalExpression"
  ) {
    return true;
  }

  if (cursor.type === "ConditionalExpression" && cursor.test) {
    return nodeText(sourceCode, cursor.test).includes(
      nodeText(sourceCode, node),
    );
  }

  return false;
}

function classify(node, sourceCode, filename, structuralImports) {
  const canonicalClass = canonicalNumericClassification(
    node,
    sourceCode,
    structuralImports,
  );
  if (canonicalClass !== undefined) {
    return canonicalClass;
  }
  const line = sourceCode.lines?.[node.loc?.start.line - 1] ?? "";
  const lineClass = classifyLine(filename, line);
  if (lineClass !== undefined) {
    return lineClass;
  }
  if (DEBUG_FILE_RE.test(filename)) {
    return "debug";
  }
  if (isInsideQuantity(node) || hasClassificationComment(sourceCode, node)) {
    return null;
  }
  if (isControlOrFormattingLiteral(node, sourceCode)) {
    return null;
  }

  const propName = attributeName(node);
  if (propName && LAYOUT_PROPS.has(propName)) {
    return "layout";
  }
  if (propName && hasAnyToken(propName, DECISION_TOKENS)) {
    return "decision";
  }

  const name = contextName(node);
  if (name === "jsx_child" && isDirectJsxChild(node)) {
    return "decision";
  }
  if (name && hasAnyToken(name, CONTROL_TOKENS)) {
    return null;
  }
  if (name && hasAnyToken(name, TELEMETRY_TOKENS)) {
    return "telemetry";
  }
  if (name && hasAnyToken(name, DECISION_TOKENS)) {
    return "decision";
  }

  return null;
}

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Require decision-bearing numeric literals to be wrapped as QuantityValue.",
    },
    schema: [
      {
        type: "object",
        properties: {
          classes: {
            type: "array",
            items: {
              enum: ["decision", "telemetry"],
              type: "string",
            },
            uniqueItems: true,
          },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      decision:
        'Decision numeric literal "{{value}}" must be emitted as QuantityValue and rendered through <Quantity>.',
      telemetry:
        'Telemetry numeric literal "{{value}}" must be explicitly annotated with policyos-quantity: telemetry.',
    },
  },
  create(context) {
    const sourceCode = context.sourceCode;
    const filename = context.filename || "";
    const options = context.options[0] || {};
    const reportedClasses = new Set(options.classes || ["decision"]);
    const structuralImports = new Map();

    function check(node) {
      if (!isNumberLiteral(node)) {
        return;
      }

      const quantityClass = classify(
        node,
        sourceCode,
        filename,
        structuralImports,
      );
      if (quantityClass !== "decision" && quantityClass !== "telemetry") {
        return;
      }
      if (!reportedClasses.has(quantityClass)) {
        return;
      }

      context.report({
        node,
        messageId: quantityClass,
        data: { value: String(node.value) },
      });
    }

    return {
      ImportDeclaration(node) {
        if (node.source.value !== NON_AUTHORITY_NUMERIC_MODULE) {
          return;
        }
        for (const specifier of node.specifiers) {
          if (specifier.type !== "ImportSpecifier") {
            continue;
          }
          const importedName = propertyName(specifier.imported);
          const classification =
            NON_AUTHORITY_NUMERIC_IMPORTS.get(importedName);
          if (classification) {
            structuralImports.set(specifier.local.name, {
              classification,
              specifier,
            });
          }
        }
      },
      Literal: check,
      NumericLiteral: check,
    };
  },
};
