#!/usr/bin/env node
/** Node recursive-descent implementation of the complete INT-R6 locale census. */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const SCHEMA_VERSION = "policyos.research.task_l.locale_leaf_census.v1";
const DECODER_ID = "node.recursive_descent.v1";

class ParseFailure extends Error {
  constructor(code, detail) {
    super(`${code}: ${detail}`);
    this.code = code;
    this.detail = detail;
  }
}

function pointer(parts) {
  return `/${parts.map((part) => part.replaceAll("~", "~0").replaceAll("/", "~1")).join("/")}`;
}

function decodeDocument(text, fileName) {
  let offset = 0;

  function fail(code, detail = `offset=${offset}`) {
    throw new ParseFailure(code, `${fileName}:${detail}`);
  }

  function skipWhitespace() {
    while (offset < text.length && /[\t\n\r ]/.test(text[offset])) offset += 1;
  }

  function parseString() {
    if (text[offset] !== '"') fail("node_recursive_string_expected");
    offset += 1;
    let result = "";
    while (offset < text.length) {
      const current = text[offset];
      offset += 1;
      if (current === '"') return result;
      if (current === "\\") {
        if (offset >= text.length) fail("node_recursive_escape_truncated");
        const escaped = text[offset];
        offset += 1;
        const simple = {
          '"': '"',
          "\\": "\\",
          "/": "/",
          b: "\b",
          f: "\f",
          n: "\n",
          r: "\r",
          t: "\t",
        };
        if (Object.hasOwn(simple, escaped)) {
          result += simple[escaped];
          continue;
        }
        if (escaped !== "u") fail("node_recursive_escape_invalid", `offset=${offset - 1}`);
        const hexadecimal = text.slice(offset, offset + 4);
        if (!/^[0-9a-fA-F]{4}$/.test(hexadecimal)) {
          fail("node_recursive_unicode_escape_invalid", `offset=${offset}`);
        }
        offset += 4;
        const high = Number.parseInt(hexadecimal, 16);
        if (
          high >= 0xd800 &&
          high <= 0xdbff &&
          text.slice(offset, offset + 2) === "\\u" &&
          /^[0-9a-fA-F]{4}$/.test(text.slice(offset + 2, offset + 6))
        ) {
          const low = Number.parseInt(text.slice(offset + 2, offset + 6), 16);
          if (low >= 0xdc00 && low <= 0xdfff) {
            result += String.fromCodePoint(0x10000 + ((high - 0xd800) << 10) + low - 0xdc00);
            offset += 6;
            continue;
          }
        }
        result += String.fromCharCode(high);
        continue;
      }
      if (current.charCodeAt(0) < 0x20) {
        fail("node_recursive_control_character", `offset=${offset - 1}`);
      }
      result += current;
    }
    fail("node_recursive_string_unterminated");
  }

  function parseNumber() {
    const remaining = text.slice(offset);
    const match = remaining.match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/);
    if (match === null) fail("node_recursive_number_invalid");
    offset += match[0].length;
    const result = Number(match[0]);
    if (!Number.isFinite(result)) fail("node_recursive_number_non_finite");
    return result;
  }

  function parseArray(parts) {
    offset += 1;
    const result = [];
    skipWhitespace();
    if (text[offset] === "]") {
      offset += 1;
      return result;
    }
    while (offset < text.length) {
      result.push(parseValue([...parts, String(result.length)]));
      skipWhitespace();
      if (text[offset] === "]") {
        offset += 1;
        return result;
      }
      if (text[offset] !== ",") fail("node_recursive_array_separator_missing");
      offset += 1;
      skipWhitespace();
    }
    fail("node_recursive_array_unterminated");
  }

  function parseObject(parts) {
    offset += 1;
    const result = Object.create(null);
    const keys = new Set();
    skipWhitespace();
    if (text[offset] === "}") {
      offset += 1;
      return result;
    }
    while (offset < text.length) {
      if (text[offset] !== '"') fail("node_recursive_object_key_expected");
      const key = parseString();
      if (keys.has(key)) {
        throw new ParseFailure("node_recursive_duplicate_key", `${fileName}:${pointer([...parts, key])}`);
      }
      keys.add(key);
      skipWhitespace();
      if (text[offset] !== ":") fail("node_recursive_object_colon_missing");
      offset += 1;
      skipWhitespace();
      result[key] = parseValue([...parts, key]);
      skipWhitespace();
      if (text[offset] === "}") {
        offset += 1;
        return result;
      }
      if (text[offset] !== ",") fail("node_recursive_object_separator_missing");
      offset += 1;
      skipWhitespace();
    }
    fail("node_recursive_object_unterminated");
  }

  function parseValue(parts) {
    skipWhitespace();
    const current = text[offset];
    if (current === "{") return parseObject(parts);
    if (current === "[") return parseArray(parts);
    if (current === '"') return parseString();
    if (text.startsWith("true", offset)) {
      offset += 4;
      return true;
    }
    if (text.startsWith("false", offset)) {
      offset += 5;
      return false;
    }
    if (text.startsWith("null", offset)) {
      offset += 4;
      return null;
    }
    if (current === "-" || /[0-9]/.test(current ?? "")) return parseNumber();
    fail("node_recursive_value_invalid", `${pointer(parts)}:offset=${offset}`);
  }

  const result = parseValue([]);
  skipWhitespace();
  if (offset !== text.length) fail("node_recursive_trailing_content");
  return result;
}

function flatten(value, parts = [], output = new Map()) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => flatten(item, [...parts, String(index)], output));
    return output;
  }
  if (value !== null && typeof value === "object") {
    Object.keys(value)
      .sort()
      .forEach((key) => flatten(value[key], [...parts, key], output));
    return output;
  }
  if (typeof value !== "string") {
    throw new ParseFailure("node_recursive_non_string_leaf", `${pointer(parts)}:${typeof value}`);
  }
  output.set(pointer(parts), value);
  return output;
}

function digestRows(rows) {
  const body = rows.map((row) => JSON.stringify(row)).join("\n");
  return `sha256:${crypto.createHash("sha256").update(body, "utf8").digest("hex")}`;
}

function buildReport(directoryArgument) {
  const directory = path.resolve(directoryArgument);
  let entries;
  try {
    entries = fs
      .readdirSync(directory, { withFileTypes: true })
      .sort((left, right) => (left.name < right.name ? -1 : left.name > right.name ? 1 : 0));
  } catch (error) {
    throw new ParseFailure("node_locale_directory_unreadable", error.constructor.name);
  }
  const unexpected = entries
    .filter((entry) => !entry.isFile() || path.extname(entry.name) !== ".json")
    .map((entry) => entry.name);
  if (unexpected.length > 0) {
    throw new ParseFailure("node_locale_entry_ambiguous", JSON.stringify(unexpected));
  }
  if (entries.length === 0) throw new ParseFailure("node_locale_directory_empty", directory);

  const leaves = new Map();
  for (const entry of entries) {
    const locale = path.basename(entry.name, ".json");
    if (leaves.has(locale)) throw new ParseFailure("node_locale_identity_duplicate", locale);
    let text;
    try {
      text = fs.readFileSync(path.join(directory, entry.name), "utf8");
    } catch (error) {
      throw new ParseFailure("node_locale_unreadable", `${entry.name}:${error.constructor.name}`);
    }
    const decoded = decodeDocument(text, entry.name);
    if (decoded === null || Array.isArray(decoded) || typeof decoded !== "object") {
      throw new ParseFailure("node_locale_root_not_object", entry.name);
    }
    leaves.set(locale, flatten(decoded));
  }
  if (!leaves.has("en")) throw new ParseFailure("node_reference_locale_missing", "en");

  const allPathSets = [...leaves.values()].map((localeLeaves) => new Set(localeLeaves.keys()));
  const union = new Set(allPathSets.flatMap((paths) => [...paths]));
  const intersection = new Set(
    [...allPathSets[0]].filter((leafPath) => allPathSets.every((paths) => paths.has(leafPath))),
  );
  const localeReports = Object.create(null);
  for (const locale of [...leaves.keys()].sort()) {
    const rows = [...leaves.get(locale).entries()].sort(([left], [right]) =>
      left < right ? -1 : left > right ? 1 : 0,
    );
    localeReports[locale] = {
      leaf_count: rows.length,
      path_digest: digestRows(rows.map(([leafPath]) => [leafPath, ""])),
      path_value_digest: digestRows(rows),
    };
  }

  const english = leaves.get("en");
  const comparisons = Object.create(null);
  for (const locale of [...leaves.keys()].sort()) {
    if (locale === "en") continue;
    const target = leaves.get(locale);
    const common = [...english.keys()].filter((leafPath) => target.has(leafPath)).sort();
    comparisons[locale] = {
      common_leaf_count: common.length,
      missing_from_target_count: [...english.keys()].filter((leafPath) => !target.has(leafPath)).length,
      target_only_count: [...target.keys()].filter((leafPath) => !english.has(leafPath)).length,
      identical_value_count: common.filter((leafPath) => english.get(leafPath) === target.get(leafPath)).length,
      different_value_count: common.filter((leafPath) => english.get(leafPath) !== target.get(leafPath)).length,
    };
  }

  return {
    schema_version: SCHEMA_VERSION,
    decoder_id: DECODER_ID,
    decoder_implementation: "standalone Node recursive-descent decoder",
    directory_files: entries.map((entry) => entry.name),
    directory_file_count: entries.length,
    union_leaf_count: union.size,
    intersection_leaf_count: intersection.size,
    locales: localeReports,
    comparisons_to_en: comparisons,
  };
}

function main(arguments_) {
  if (arguments_.length !== 1) {
    process.stderr.write("usage: locale_census.mjs LOCALE_DIRECTORY\n");
    return 2;
  }
  try {
    const report = buildReport(arguments_[0]);
    process.stdout.write(`${JSON.stringify(report)}\n`);
    return 0;
  } catch (error) {
    if (error instanceof ParseFailure) {
      process.stderr.write(`${error.code}: ${error.detail}\n`);
      return 2;
    }
    throw error;
  }
}

process.exitCode = main(process.argv.slice(2));
