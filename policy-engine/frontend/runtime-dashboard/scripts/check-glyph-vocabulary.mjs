#!/usr/bin/env node
/**
 * Parses docs/brand/GLYPH_SPECIFICATION.md and compares its ten-radical
 * table with the GLYPH_NAMES + DOMAIN_VOCABULARY exported from
 * src/shared/brand/glyph-vocabulary.ts. Fails the build if any radical
 * or vocabulary term is in one source but not the other.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoDashboard = path.resolve(__dirname, "..");
const repoRoot = path.resolve(repoDashboard, "..", "..");

const SPEC_PATH = path.join(
  repoRoot,
  "docs",
  "brand",
  "GLYPH_SPECIFICATION.md",
);
const VOCAB_PATH = path.join(
  repoDashboard,
  "src",
  "shared",
  "brand",
  "glyph-vocabulary.ts",
);

function extractFromVocabulary(source) {
  const namesMatch = source.match(
    /export const GLYPH_NAMES = \[\n([\s\S]*?)\n\] as const;/,
  );
  if (!namesMatch) {
    throw new Error(
      `Unable to locate GLYPH_NAMES in ${VOCAB_PATH}. Did the export shape change?`,
    );
  }
  const names = Array.from(namesMatch[1].matchAll(/"([^"]+)"/g)).map(
    (match) => match[1],
  );

  const vocabMatch = source.match(
    /export const DOMAIN_VOCABULARY: Record<string, GlyphName> = \{\n([\s\S]*?)\n\};/,
  );
  if (!vocabMatch) {
    throw new Error(
      `Unable to locate DOMAIN_VOCABULARY in ${VOCAB_PATH}. Did the export shape change?`,
    );
  }
  const entries = [];
  for (const line of vocabMatch[1].split("\n")) {
    const trimmed = line.trim().replace(/^"/, "");
    if (!trimmed) continue;
    const pair = trimmed.match(/^"?([A-Za-z0-9_-]+)"?:\s*"([^"]+)"/);
    if (pair) {
      entries.push({ term: pair[1], glyph: pair[2] });
    }
  }
  return { names, entries };
}

function extractFromSpec(source) {
  const tableMatch = source.match(
    /## 3\. The ten radicals[\s\S]*?\| # \| Name \|[\s\S]*?\n([\s\S]*?)\n\n## 4/,
  );
  if (!tableMatch) {
    throw new Error(
      `Unable to find '## 3. The ten radicals' table in ${SPEC_PATH}.`,
    );
  }
  const lines = tableMatch[1].split("\n").filter((line) => line.startsWith("|"));
  const names = [];
  const entries = [];
  for (const line of lines) {
    if (/^\|\s*---/.test(line)) continue;
    if (/^\|\s*#\s*\|/.test(line)) continue;
    const columns = line
      .split("|")
      .slice(1, -1)
      .map((col) => col.trim());
    if (columns.length < 4) continue;
    const nameCell = columns[1].replace(/`/g, "").trim();
    const vocabCell = columns[3];
    if (!nameCell) continue;
    names.push(nameCell);
    for (const term of vocabCell.split(",")) {
      const clean = term.trim();
      if (clean) entries.push({ term: clean, glyph: nameCell });
    }
  }
  return { names, entries };
}

function diffArrays(label, expected, actual) {
  const missing = expected.filter((value) => !actual.includes(value));
  const extra = actual.filter((value) => !expected.includes(value));
  if (missing.length === 0 && extra.length === 0) return null;
  return { label, missing, extra };
}

function diffVocabulary(specEntries, codeEntries) {
  const specMap = new Map(specEntries.map((e) => [e.term, e.glyph]));
  const codeMap = new Map(codeEntries.map((e) => [e.term, e.glyph]));
  const missing = [];
  const extra = [];
  const mismatches = [];
  for (const [term, glyph] of specMap) {
    if (!codeMap.has(term)) {
      missing.push(term);
      continue;
    }
    const actual = codeMap.get(term);
    if (actual !== glyph) {
      mismatches.push({ term, spec: glyph, code: actual });
    }
  }
  for (const term of codeMap.keys()) {
    if (!specMap.has(term)) extra.push(term);
  }
  return { missing, extra, mismatches };
}

async function main() {
  const [specSource, vocabSource] = await Promise.all([
    readFile(SPEC_PATH, "utf8"),
    readFile(VOCAB_PATH, "utf8"),
  ]);
  const spec = extractFromSpec(specSource);
  const code = extractFromVocabulary(vocabSource);
  const errors = [];

  const namesDiff = diffArrays("GLYPH_NAMES", spec.names, code.names);
  if (namesDiff) errors.push(namesDiff);

  const vocabDiff = diffVocabulary(spec.entries, code.entries);
  if (
    vocabDiff.missing.length > 0 ||
    vocabDiff.extra.length > 0 ||
    vocabDiff.mismatches.length > 0
  ) {
    errors.push({ label: "DOMAIN_VOCABULARY", ...vocabDiff });
  }

  if (errors.length > 0) {
    console.error(
      "Glyph vocabulary mismatch between docs/brand/GLYPH_SPECIFICATION.md and glyph-vocabulary.ts:",
    );
    for (const error of errors) {
      console.error(`  ${error.label}:`);
      if (error.missing && error.missing.length > 0) {
        console.error(`    missing from code: ${error.missing.join(", ")}`);
      }
      if (error.extra && error.extra.length > 0) {
        console.error(`    extra in code: ${error.extra.join(", ")}`);
      }
      if (error.mismatches && error.mismatches.length > 0) {
        for (const mismatch of error.mismatches) {
          console.error(
            `    mismatch: ${mismatch.term} (spec=${mismatch.spec}, code=${mismatch.code})`,
          );
        }
      }
    }
    process.exit(1);
  }
  console.log(
    `OK — ${code.names.length} radicals, ${code.entries.length} vocabulary terms aligned.`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
