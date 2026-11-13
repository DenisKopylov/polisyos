import type { DecisionGrade } from "@polisyos/runtime-api-client";
import { isDecisionGrade } from "@/shared/lib/domain/decisionGrade";

export type DecisionGradePresentation =
  | Readonly<{
      classification: "recognized";
      ownerLabel: DecisionGrade;
    }>
  | Readonly<{
      classification: "unrecognized";
      ownerLabel: string | null;
    }>;

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
      ownerLabel,
    });
  }

  return Object.freeze({
    classification: "unrecognized" as const,
    ownerLabel,
  });
}
