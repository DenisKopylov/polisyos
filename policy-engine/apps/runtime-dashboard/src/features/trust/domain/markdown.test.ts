import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { splitMarkdownTableRow } from "./markdown";

const vectors = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      "../../tests/fixtures/common/markdown_table_rows.json",
    ),
    "utf8",
  ),
) as { rows: Array<{ name: string; text: string; cells: string[] }> };

describe("source-preserving Markdown table tokenizer", () => {
  it.each(vectors.rows)("$name", ({ text, cells }) => {
    expect(splitMarkdownTableRow(text)).toEqual(cells);
  });
});
