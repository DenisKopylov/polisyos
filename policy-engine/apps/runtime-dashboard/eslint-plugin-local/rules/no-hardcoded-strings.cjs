"use strict";

const ALLOWED_TEXT = new Set(["Atlas", "PolicyOS", "PolisyOS"]);
const CHECKED_ATTRIBUTES = new Set([
  "alt",
  "aria-label",
  "placeholder",
  "title",
]);
const CODE_LIKE_TAGS = new Set(["code", "kbd", "pre", "script", "style"]);

function hasLetters(text) {
  return /\p{L}/u.test(text);
}

function isMetadataLike(text) {
  return /^[A-Z0-9_./:-]+$/u.test(text);
}

function normalizeText(text) {
  return text.replace(/\s+/gu, " ").trim();
}

function shouldSkipText(text) {
  const normalized = normalizeText(text);

  if (!normalized) {
    return true;
  }

  if (!hasLetters(normalized)) {
    return true;
  }

  if (ALLOWED_TEXT.has(normalized)) {
    return true;
  }

  if (isMetadataLike(normalized)) {
    return true;
  }

  return false;
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
    type: "problem",
    docs: {
      description:
        "Disallow hardcoded user-facing strings in JSX — route visible copy through the i18n catalog.",
    },
    schema: [],
    messages: {
      hardcoded:
        'Hardcoded user-facing string "{{text}}" is not allowed in JSX. Move it into the i18n catalog and render it via t("...").',
    },
  },
  create(context) {
    return {
      JSXText(node) {
        if (isInsideCodeLikeElement(node) || shouldSkipText(node.value)) {
          return;
        }

        context.report({
          node,
          messageId: "hardcoded",
          data: {
            text: normalizeText(node.value).slice(0, 80),
          },
        });
      },
      Literal(node) {
        const attributeName = getAttributeName(node);
        if (
          typeof node.value !== "string" ||
          attributeName === null ||
          !CHECKED_ATTRIBUTES.has(attributeName) ||
          shouldSkipText(node.value)
        ) {
          return;
        }

        context.report({
          node,
          messageId: "hardcoded",
          data: {
            text: normalizeText(node.value).slice(0, 80),
          },
        });
      },
    };
  },
};
