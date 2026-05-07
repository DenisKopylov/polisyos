import {
  flattenBureaucraticBlocks,
  type BureaucraticDocumentAST,
  type BureaucraticEpistemicKind,
  type BureaucraticEpistemicSummary,
} from "./bureaucratic-document-ast";

const ORIGINS: BureaucraticEpistemicKind[] = [
  "evidence_filled",
  "model_generated",
  "operator_filled",
  "imported",
];

export function computeEpistemicSummary(
  document: Pick<BureaucraticDocumentAST, "annexes" | "blocks">,
): BureaucraticEpistemicSummary {
  const blocks = flattenBureaucraticBlocks(document);
  const counts = Object.fromEntries(
    ORIGINS.map((origin) => [origin, 0]),
  ) as Record<BureaucraticEpistemicKind, number>;
  for (const block of blocks) {
    counts[block.epistemic_origin] += 1;
  }
  const total = Math.max(1, blocks.length);
  return {
    evidence_filled: roundShare(counts.evidence_filled / total),
    model_generated: roundShare(counts.model_generated / total),
    operator_filled: roundShare(counts.operator_filled / total),
    imported: roundShare(counts.imported / total),
  };
}

export function epistemicLabel(origin: BureaucraticEpistemicKind): string {
  switch (origin) {
    case "evidence_filled":
      return "Evidence-filled";
    case "model_generated":
      return "Model-generated";
    case "operator_filled":
      return "Operator-filled";
    case "imported":
      return "Imported";
  }
}

function roundShare(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}
