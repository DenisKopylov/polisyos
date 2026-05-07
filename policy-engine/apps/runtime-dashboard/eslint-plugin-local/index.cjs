"use strict";

const brandRoleSeparation = require("./rules/brand-role-separation.cjs");
const noHardcodedStrings = require("./rules/no-hardcoded-strings.cjs");
const noRawEmojiInJsx = require("./rules/no-raw-emoji-in-jsx.cjs");
const quantityMustBeWrapped = require("./rules/quantity-must-be-wrapped.cjs");
const requireAuthoredTextInProse = require("./rules/require-authored-text-in-prose.cjs");
const requireNonBreakingSpaceForShortPrepositions = require("./rules/require-non-breaking-space-for-short-prepositions.cjs");

module.exports = {
  meta: {
    name: "eslint-plugin-local",
    version: "0.1.0",
  },
  rules: {
    "brand-role-separation": brandRoleSeparation,
    "no-hardcoded-strings": noHardcodedStrings,
    "no-raw-emoji-in-jsx": noRawEmojiInJsx,
    "quantity-must-be-wrapped": quantityMustBeWrapped,
    "require-authored-text-in-prose": requireAuthoredTextInProse,
    "require-non-breaking-space-for-short-prepositions":
      requireNonBreakingSpaceForShortPrepositions,
  },
};
