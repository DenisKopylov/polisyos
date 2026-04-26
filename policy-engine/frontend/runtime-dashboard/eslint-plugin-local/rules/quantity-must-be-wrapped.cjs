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
  let cursor = node.parent;
  if (cursor && cursor.type === "UnaryExpression") {
    cursor = cursor.parent;
  }
  return cursor?.type === "JSXExpressionContainer";
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

function classify(node, sourceCode, filename) {
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

    function check(node) {
      if (!isNumberLiteral(node)) {
        return;
      }

      const quantityClass = classify(node, sourceCode, filename);
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
      Literal: check,
      NumericLiteral: check,
    };
  },
};
