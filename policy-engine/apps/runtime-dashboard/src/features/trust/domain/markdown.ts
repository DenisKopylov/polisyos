/** Split source cells without unescaping, trimming or admitting their semantics. */
export function splitMarkdownTableRow(text: string): string[] {
  // Equal-length maximal backtick runs delimit code; unmatched runs are literal.
  const runs = [...text.matchAll(/`+/gu)];
  const nextEndByWidth = new Map<number, number>();
  const codeRuns = new Map<number, { end: number; closingEnd?: number }>();
  for (const run of runs.reverse()) {
    const start = run.index;
    const width = run[0].length;
    const end = start + width;
    codeRuns.set(start, { end, closingEnd: nextEndByWidth.get(width) });
    nextEndByWidth.set(width, end);
  }

  const cells: string[] = [];
  let start = 0;
  let index = 0;
  while (index < text.length) {
    const character = text[index];
    if (character === "\\") {
      index += 2;
      continue;
    }
    const codeRun = codeRuns.get(index);
    if (codeRun) {
      index = codeRun.closingEnd ?? codeRun.end;
      continue;
    }
    if (character === "|") {
      cells.push(text.slice(start, index));
      start = index + 1;
    }
    index += 1;
  }
  cells.push(text.slice(start));

  // Discard only optional outer delimiters and padding outside those delimiters.
  if (cells.length > 1 && cells[0]!.trim() === "") cells.shift();
  if (cells.length > 1 && cells.at(-1)!.trim() === "") cells.pop();
  return cells;
}
