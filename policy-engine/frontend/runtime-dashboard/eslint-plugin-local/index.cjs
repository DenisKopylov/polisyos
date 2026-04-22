"use strict";

const noRawEmojiInJsx = require("./rules/no-raw-emoji-in-jsx.cjs");

module.exports = {
  meta: {
    name: "eslint-plugin-local",
    version: "0.1.0",
  },
  rules: {
    "no-raw-emoji-in-jsx": noRawEmojiInJsx,
  },
};
