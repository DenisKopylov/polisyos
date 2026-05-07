import type { BureaucraticBlock } from "./bureaucratic-document-ast";

const ROMAN = [
  "",
  "I",
  "II",
  "III",
  "IV",
  "V",
  "VI",
  "VII",
  "VIII",
  "IX",
  "X",
] as const;

type Counters = {
  annex: number;
  article: number;
  clause: number;
  section: number;
  subclause: number;
};

export function numberBureaucraticBlocks(
  blocks: BureaucraticBlock[],
): BureaucraticBlock[] {
  const counters: Counters = {
    annex: 0,
    article: 0,
    clause: 0,
    section: 0,
    subclause: 0,
  };

  return blocks.map((block) => numberBlock(block, counters));
}

export function labelAnnex(index: number): string {
  return `Додаток ${index}`;
}

export function labelSection(index: number): string {
  return `Розділ ${ROMAN[index] ?? index}`;
}

function numberBlock(
  block: BureaucraticBlock,
  counters: Counters,
): BureaucraticBlock {
  const number = numberForKind(block, counters);
  const children = block.children?.map((child) =>
    numberBlock(child, counters),
  );
  return {
    ...block,
    children,
    number: block.number ?? number,
  };
}

function numberForKind(
  block: BureaucraticBlock,
  counters: Counters,
): string | null {
  switch (block.kind) {
    case "annex":
      counters.annex += 1;
      return labelAnnex(counters.annex);
    case "section":
      counters.section += 1;
      counters.article = 0;
      counters.clause = 0;
      counters.subclause = 0;
      return labelSection(counters.section);
    case "article":
      counters.article += 1;
      counters.clause = 0;
      counters.subclause = 0;
      return `Стаття ${counters.article}`;
    case "clause":
      counters.clause += 1;
      counters.subclause = 0;
      return `${counters.clause}.`;
    case "subclause":
      counters.subclause += 1;
      return `${counters.clause}.${counters.subclause}.`;
    default:
      return null;
  }
}
