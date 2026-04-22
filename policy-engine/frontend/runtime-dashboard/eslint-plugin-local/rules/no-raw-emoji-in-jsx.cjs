/**
 * Forbid raw emoji or decorative Unicode glyphs in JSX text content and
 * string attributes. The PolicyOS alphabet is the ten-radical set defined
 * in docs/brand/GLYPH_SPECIFICATION.md — use <Glyph name="..."> instead of
 * pasting `⊙`, `◫`, `◷`, etc. directly.
 *
 * Scope:
 *   - JSX text nodes (JSXText)
 *   - String attribute values (Literal child of JSXAttribute.value)
 * Exemptions:
 *   - The documentation files themselves (*.md).
 *   - Files under `src/shared/brand/glyph-vocabulary.ts` that encode the
 *     canonical Unicode anchors.
 */

"use strict";

const FORBIDDEN_RANGES = [
  [0x2190, 0x21ff], // Arrows
  [0x2200, 0x22ff], // Mathematical operators
  [0x2300, 0x23ff], // Miscellaneous technical
  [0x25a0, 0x25ff], // Geometric shapes
  [0x2600, 0x26ff], // Misc symbols
  [0x2700, 0x27bf], // Dingbats
  [0x27c0, 0x27ef], // Misc mathematical symbols-A
  [0x27f0, 0x27ff], // Supplemental arrows-A
  [0x2900, 0x297f], // Supplemental arrows-B
  [0x2b00, 0x2bff], // Misc symbols and arrows
  [0x1f300, 0x1fbff], // Pictographs, emoji, symbols
];

function isForbidden(codePoint) {
  for (const [lo, hi] of FORBIDDEN_RANGES) {
    if (codePoint >= lo && codePoint <= hi) return true;
  }
  return false;
}

function firstForbidden(text) {
  if (typeof text !== "string") return null;
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    if (cp !== undefined && isForbidden(cp)) {
      return { char: ch, codePoint: cp };
    }
  }
  return null;
}

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow raw emoji / decorative Unicode glyphs in JSX — use <Glyph /> or <JanusGlyph /> from shared/brand.",
    },
    schema: [],
    messages: {
      forbidden:
        "Raw decorative glyph U+{{hex}} ('{{char}}') is not allowed in JSX. Use <Glyph name=\"...\"/> from @/shared/brand instead.",
    },
  },
  create(context) {
    const filename = context.filename ?? context.getFilename?.() ?? "";
    if (
      filename.endsWith(".md") ||
      filename.includes("glyph-vocabulary") ||
      filename.includes("no-raw-emoji-in-jsx")
    ) {
      return {};
    }
    return {
      JSXText(node) {
        const found = firstForbidden(node.value);
        if (found) {
          context.report({
            node,
            messageId: "forbidden",
            data: {
              char: found.char,
              hex: found.codePoint.toString(16).toUpperCase(),
            },
          });
        }
      },
      Literal(node) {
        if (
          node.parent &&
          node.parent.type === "JSXAttribute" &&
          typeof node.value === "string"
        ) {
          const found = firstForbidden(node.value);
          if (found) {
            context.report({
              node,
              messageId: "forbidden",
              data: {
                char: found.char,
                hex: found.codePoint.toString(16).toUpperCase(),
              },
            });
          }
        }
      },
    };
  },
};
