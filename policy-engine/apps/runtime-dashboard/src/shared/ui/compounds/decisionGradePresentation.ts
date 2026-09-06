import type { DecisionGrade } from "@polisyos/runtime-api-client";

export type DecisionGradePresentation =
  | Readonly<{
      classification: "recognized";
      ownerLabel: DecisionGrade;
    }>
  | Readonly<{
      classification: "unrecognized";
      ownerLabel: string | null;
    }>;

const decisionGradePresentationByOwnerGrade = {
  unsupported: "unsupported",
  descriptive_only: "descriptive_only",
  advisory_admissible: "advisory_admissible",
  decision_admissible: "decision_admissible",
} as const satisfies Record<DecisionGrade, DecisionGrade>;

function isDecisionGrade(ownerLabel: string): ownerLabel is DecisionGrade {
  return Object.hasOwn(decisionGradePresentationByOwnerGrade, ownerLabel);
}

/**
 * Presents an owner-issued decision grade without inventing frontend authority.
 *
 * This is the single swap point for the generated DecisionGrade union.
 */
export function presentDecisionGradeLabel(
  ownerValue: unknown,
): DecisionGradePresentation {
  const ownerLabel =
    typeof ownerValue === "string" && ownerValue.trim()
      ? ownerValue.trim()
      : null;

  if (ownerLabel !== null && isDecisionGrade(ownerLabel)) {
    return Object.freeze({
      classification: "recognized" as const,
      ownerLabel: decisionGradePresentationByOwnerGrade[ownerLabel],
    });
  }

  return Object.freeze({
    classification: "unrecognized" as const,
    ownerLabel,
  });
}
