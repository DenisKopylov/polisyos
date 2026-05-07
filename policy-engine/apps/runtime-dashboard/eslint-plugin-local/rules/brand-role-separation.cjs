"use strict";

const TEST_OR_STORY_FILE = /\.(?:test|a11y\.test|stories)\.[cm]?[jt]sx?$/u;

const PRODUCT_SURFACE_PATTERNS = [
  /\/src\/app\/layout\//u,
  /\/src\/features\/clerk\//u,
  /\/src\/shared\/ui\/responsive\//u,
];

const PUBLIC_SURFACE_PATTERNS = [/\/src\/features\/landing\//u];

const ATLAS_ALLOWLIST_PATTERNS = [
  /\/src\/features\/runs\/components\/AtlasRunDeck\.tsx$/u,
];

function matchesAny(filename, patterns) {
  return patterns.some((pattern) => pattern.test(filename));
}

function readElementName(node) {
  if (node.type !== "JSXIdentifier") {
    return null;
  }
  return node.name;
}

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Enforce ADR-042 role separation between AtlasBrand and JanusGlyph.",
    },
    schema: [],
    messages: {
      atlasInProduct:
        "AtlasBrand is reserved for public/external surfaces. Use JanusGlyph on product chrome and authenticated runtime viewports.",
      janusInPublic:
        "JanusGlyph is reserved for in-product surfaces. Use AtlasBrand on landing and other public surfaces.",
    },
  },
  create(context) {
    const filename = context.filename ?? context.getFilename?.() ?? "";
    if (TEST_OR_STORY_FILE.test(filename)) {
      return {};
    }

    return {
      JSXOpeningElement(node) {
        const name = readElementName(node.name);
        if (!name) {
          return;
        }

        if (
          name === "AtlasBrand" &&
          matchesAny(filename, PRODUCT_SURFACE_PATTERNS) &&
          !matchesAny(filename, ATLAS_ALLOWLIST_PATTERNS)
        ) {
          context.report({
            node,
            messageId: "atlasInProduct",
          });
        }

        if (
          name === "JanusGlyph" &&
          matchesAny(filename, PUBLIC_SURFACE_PATTERNS)
        ) {
          context.report({
            node,
            messageId: "janusInPublic",
          });
        }
      },
    };
  },
};
