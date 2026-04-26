"use strict";

const LAYOUT_PROPS = new Set([
  "cx",
  "cy",
  "d",
  "height",
  "left",
  "r",
  "size",
  "strokeWidth",
  "top",
  "width",
  "x",
  "x1",
  "x2",
  "y",
  "y1",
  "y2",
]);

const DECISION_TOKENS = [
  "budget",
  "confidence",
  "cost",
  "delta",
  "effect",
  "estimate",
  "metric",
  "probability",
  "rate",
  "risk",
  "score",
  "value",
];

const TELEMETRY_TOKENS = [
  "byte",
  "cache",
  "count",
  "duration",
  "event",
  "latency",
  "ms",
  "total",
];

const CONTROL_TOKENS = [
  "axis",
  "avg",
  "bucket",
  "column",
  "diagnostic",
  "digit",
  "fraction",
  "gap",
  "index",
  "issue",
  "length",
  "limit",
  "max",
  "min",
  "offset",
  "page",
  "precision",
  "row",
  "slice",
  "step",
  "sum",
  "threshold",
];

const CONTROL_CALLS = new Set([
  "ceil",
  "floor",
  "map",
  "max",
  "min",
  "padEnd",
  "padStart",
  "reduce",
  "round",
  "slice",
  "splice",
  "substr",
  "substring",
  "toFixed",
  "toLocaleString",
  "toPrecision",
]);

const FORMAT_OPTION_PROPS = new Set([
  "maximumFractionDigits",
  "minimumFractionDigits",
  "minimumIntegerDigits",
  "precision",
]);

const DEBUG_FILE_RE =
  /(\.test\.|\.stories\.|__fixtures__|fixtures|mocks|mock|\/src\/test\/)/u;

function hasAnyToken(value, tokens) {
  const normalized = String(value || "").toLowerCase();
  return tokens.some((token) => normalized.includes(token));
}

function lineHasClassificationComment(line) {
  return /policyos-quantity:\s*(telemetry|layout|debug)/iu.test(line);
}

function classifyLine(filePath, line) {
  if (DEBUG_FILE_RE.test(filePath)) {
    return "debug";
  }
  if (
    /frontend\/runtime-dashboard\/src\/(shared\/charts|features\/causal|app\/layout)\//u.test(
      filePath,
    )
  ) {
    return "layout";
  }
  if (lineHasClassificationComment(line)) {
    return null;
  }
  if (
    /\b(className|style|viewBox|aria-|data-|grid|width|height|padding|radius|strokeWidth|fontSize|fontWeight|fillOpacity|opacity|size|estimateSize|number|cx|cy|r|rx|PADDING|SVG_|PLOT_|MAIN_|DIFF_|GAP_)\b/u.test(
      line,
    )
  ) {
    return "layout";
  }
  if (
    /\b(reduce|Math\.(min|max|round|floor|ceil)|values\.length|items\.length|slice|toFixed|toLocaleString)\b/u.test(
      line,
    )
  ) {
    return null;
  }
  if (hasAnyToken(line, CONTROL_TOKENS)) {
    return null;
  }
  if (hasAnyToken(line, TELEMETRY_TOKENS)) {
    return "telemetry";
  }
  if (
    />\s*-?\d+(?:\.\d+)?\s*</u.test(line) ||
    /\{\s*-?\d+(?:\.\d+)?\s*\}/u.test(line)
  ) {
    return "decision";
  }
  if (
    /(?:value|score|risk|rate|effect|budget|cost|confidence|probability)\s*=\s*\{\s*-?\d+(?:\.\d+)?\s*\}/iu.test(
      line,
    )
  ) {
    return "decision";
  }
  return "telemetry";
}

module.exports = {
  CONTROL_CALLS,
  CONTROL_TOKENS,
  DEBUG_FILE_RE,
  DECISION_TOKENS,
  FORMAT_OPTION_PROPS,
  LAYOUT_PROPS,
  TELEMETRY_TOKENS,
  classifyLine,
  hasAnyToken,
  lineHasClassificationComment,
};
