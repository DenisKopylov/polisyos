import { describe, expect, it } from "vitest";

import type { BureaucraticBlock } from "./bureaucratic-document-ast";
import {
  labelAnnex,
  labelSection,
  numberBureaucraticBlocks,
} from "./numbering";

const base = {
  authorship: {
    author: "PolicyOS",
    author_role: "system",
    reviewed_by_human: false,
  },
  epistemic_origin: "model_generated" as const,
  level: 1,
};

describe("bureaucratic numbering", () => {
  it("labels sections, articles, clauses, subclauses and annexes", () => {
    const blocks: BureaucraticBlock[] = [
      { ...base, id: "s1", kind: "section", title: "One" },
      { ...base, id: "a1", kind: "article", title: "Article" },
      { ...base, id: "c1", kind: "clause", text: "Clause" },
      { ...base, id: "sc1", kind: "subclause", text: "Subclause" },
      { ...base, id: "annex", kind: "annex", title: "Annex" },
    ];

    const numbered = numberBureaucraticBlocks(blocks);

    expect(numbered.map((block) => block.number)).toEqual([
      "Розділ I",
      "Стаття 1",
      "1.",
      "1.1.",
      "Додаток 1",
    ]);
    expect(labelSection(2)).toBe("Розділ II");
    expect(labelAnnex(3)).toBe("Додаток 3");
  });
});
