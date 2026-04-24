"use strict";

function getJsxName(node) {
  if (!node) {
    return null;
  }

  if (node.type === "JSXIdentifier") {
    return node.name;
  }

  if (node.type === "JSXMemberExpression") {
    return getJsxName(node.property);
  }

  return null;
}

function getAttribute(openingElement, attributeName) {
  return (
    openingElement.attributes.find(
      (attribute) =>
        attribute.type === "JSXAttribute" &&
        getJsxName(attribute.name) === attributeName,
    ) ?? null
  );
}

function readLiteralExpression(expression) {
  if (!expression) {
    return null;
  }

  if (expression.type === "Literal") {
    return expression.value;
  }

  if (
    expression.type === "JSXExpressionContainer" &&
    expression.expression.type === "Literal"
  ) {
    return expression.expression.value;
  }

  return null;
}

function isTruthyAttribute(attribute) {
  if (!attribute) {
    return false;
  }

  if (attribute.value == null) {
    return true;
  }

  const value = readLiteralExpression(attribute.value);
  return value === true || value === "true";
}

function readStringAttribute(attribute) {
  if (!attribute || attribute.value == null) {
    return null;
  }

  if (attribute.value.type === "Literal") {
    return typeof attribute.value.value === "string"
      ? attribute.value.value.trim()
      : null;
  }

  if (
    attribute.value.type === "JSXExpressionContainer" &&
    attribute.value.expression.type === "Literal" &&
    typeof attribute.value.expression.value === "string"
  ) {
    return attribute.value.expression.value.trim();
  }

  return null;
}

function getOpeningElement(element) {
  return element && element.type === "JSXElement"
    ? element.openingElement
    : null;
}

function findAncestorElement(node, predicate) {
  let current = node.parent;

  while (current) {
    if (current.type === "JSXElement" && predicate(current)) {
      return current;
    }
    current = current.parent;
  }

  return null;
}

function findExemption(element) {
  let current = element;

  while (current) {
    if (current.type === "JSXElement") {
      const openingElement = getOpeningElement(current);
      const exemptAttribute = getAttribute(
        openingElement,
        "data-authored-exempt",
      );
      if (isTruthyAttribute(exemptAttribute)) {
        const reason = readStringAttribute(
          getAttribute(openingElement, "data-authored-exempt-reason"),
        );
        return {
          element: current,
          hasReason: Boolean(reason),
        };
      }
    }

    current = current.parent;
  }

  return null;
}

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Require prose paragraphs in narrative-bearing surfaces to be wrapped by AuthoredText or explicitly exempted.",
    },
    schema: [],
    messages: {
      missingAuthoredText:
        'Wrap prose paragraphs in <AuthoredText> or mark a structural chrome container with data-authored-exempt="true" and data-authored-exempt-reason.',
      missingExemptionReason:
        "data-authored-exempt requires a non-empty data-authored-exempt-reason so the prose exemption stays auditable.",
    },
  },
  create(context) {
    return {
      JSXOpeningElement(node) {
        if (getJsxName(node.name) !== "p") {
          return;
        }

        const paragraphElement =
          node.parent && node.parent.type === "JSXElement" ? node.parent : null;
        if (!paragraphElement) {
          return;
        }

        const authoredAncestor = findAncestorElement(
          paragraphElement,
          (element) =>
            getJsxName(getOpeningElement(element)?.name) === "AuthoredText",
        );
        if (authoredAncestor) {
          return;
        }

        const exemption = findExemption(paragraphElement);
        if (exemption) {
          if (!exemption.hasReason) {
            context.report({
              node: getOpeningElement(exemption.element),
              messageId: "missingExemptionReason",
            });
          }
          return;
        }

        context.report({
          node,
          messageId: "missingAuthoredText",
        });
      },
    };
  },
};
