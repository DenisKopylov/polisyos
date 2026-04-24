"use strict";

const CHECKED_ATTRIBUTES = new Set([
  "alt",
  "aria-label",
  "placeholder",
  "title",
]);
const CODE_LIKE_TAGS = new Set(["code", "kbd", "pre", "script", "style"]);
const SHORT_PREPOSITIONS = [
  "в",
  "у",
  "з",
  "і",
  "й",
  "та",
  "на",
  "до",
  "від",
  "за",
  "під",
  "над",
  "про",
  "о",
  "к",
  "с",
  "и",
  "а",
  "но",
];

const NBSP = "\u00A0";
const SHORT_PREPOSITION_PATTERN = new RegExp(
  `(^|[\\s(\\[{"«„“])(${SHORT_PREPOSITIONS.join("|")})(?:[ \\t]+)(?=\\S)`,
  "giu",
);

function insertNbsp(text) {
  return text.replace(SHORT_PREPOSITION_PATTERN, (_match, prefix, word) => {
    return `${prefix}${word}${NBSP}`;
  });
}

function readJsxTagName(element) {
  const openingElement = element.openingElement;
  if (!openingElement) {
    return null;
  }

  const { name } = openingElement;
  return name && name.type === "JSXIdentifier" ? name.name : null;
}

function isInsideCodeLikeElement(node) {
  const element =
    node.parent && node.parent.type === "JSXElement" ? node.parent : null;
  if (!element) {
    return false;
  }

  const tagName = readJsxTagName(element);
  return tagName !== null && CODE_LIKE_TAGS.has(tagName);
}

function getAttributeName(node) {
  if (
    !node.parent ||
    node.parent.type !== "JSXAttribute" ||
    node.parent.name.type !== "JSXIdentifier"
  ) {
    return null;
  }

  return node.parent.name.name;
}

module.exports = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Require non-breaking spaces after short Ukrainian and Russian prepositions in JSX string literals.",
    },
    fixable: "code",
    schema: [],
    messages: {
      missingNbsp:
        "Use a non-breaking space after short Ukrainian/Russian prepositions.",
    },
  },
  create(context) {
    return {
      JSXText(node) {
        if (isInsideCodeLikeElement(node)) {
          return;
        }

        const fixed = insertNbsp(node.value);
        if (fixed === node.value) {
          return;
        }

        context.report({
          node,
          messageId: "missingNbsp",
          fix(fixer) {
            return fixer.replaceText(node, fixed);
          },
        });
      },
      Literal(node) {
        const attributeName = getAttributeName(node);
        if (
          typeof node.value !== "string" ||
          attributeName === null ||
          !CHECKED_ATTRIBUTES.has(attributeName)
        ) {
          return;
        }

        const fixed = insertNbsp(node.value);
        if (fixed === node.value) {
          return;
        }

        context.report({
          node,
          messageId: "missingNbsp",
          fix(fixer) {
            return fixer.replaceText(node, JSON.stringify(fixed));
          },
        });
      },
    };
  },
};
