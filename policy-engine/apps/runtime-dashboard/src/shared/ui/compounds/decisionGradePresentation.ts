export type DecisionGradePresentation = Readonly<{
  classification: "unrecognized";
  ownerLabel: string | null;
}>;

/**
 * Presents an owner-issued decision grade without inventing frontend authority.
 *
 * This is the single swap point for the future generated DecisionGrade union.
 */
export function presentDecisionGradeLabel(
  ownerValue: unknown,
): DecisionGradePresentation {
  const ownerLabel =
    typeof ownerValue === "string" && ownerValue.trim()
      ? ownerValue.trim()
      : null;

  return Object.freeze({
    classification: "unrecognized" as const,
    ownerLabel,
  });
}
